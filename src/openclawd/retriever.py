"""Hybrid retrieval engine: vector + BM25 fusion with decay scoring.

Port of memory-lancedb-pro's retriever.ts fusion logic. Runs vector
search and FTS search in parallel on LanceDB, fuses with weighted sum,
applies the decay engine's search boost.

Reference: references/source-algorithms.md § Hybrid retrieval fusion
Source:    CortexReach/memory-lancedb-pro src/retriever.ts:1109-1186
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from . import config
from .decay import DecayableMemory, apply_search_boost

logger = logging.getLogger("openclawd")

# --- Fusion config (matches memory-lancedb-pro defaults) ---

VECTOR_WEIGHT = 0.7
BM25_WEIGHT = 0.3
BM25_EXACT_FLOOR = 0.75     # BM25 hits ≥ this get preserved even if vector is weak
BM25_FLOOR_FACTOR = 0.92    # multiplier for exact-match floor: max(fused, bm25 * 0.92)
SCORE_CLAMP_MIN = 0.1
HARD_MIN_SCORE = 0.35       # results below this are dropped post-fusion


@dataclass
class ScoredMemory:
    """A memory with its fused + decay-boosted score."""
    id: str
    content: str
    abstract: str
    category: str
    project: str
    tags: str
    importance: int
    tier: str
    scope: str
    confidence: float
    score: float              # final score after fusion + decay boost
    vector_score: float       # cosine similarity [0, 1]
    bm25_score: float         # FTS relevance [0, 1]


def _ensure_fts_index(table) -> bool:
    """Create FTS index on content column if it doesn't exist. Returns True on success."""
    try:
        table.create_fts_index("content", replace=True)
        return True
    except Exception as e:
        logger.debug("FTS index creation skipped: %s", e)
        return False


def _vector_search(table, query_vector: list[float], pool_size: int, where: str) -> dict[str, dict]:
    """Run cosine vector search, return {id: {row_data + vector_score}}."""
    search = table.search(query_vector, query_type="vector").metric("cosine").limit(pool_size)
    if where:
        search = search.where(where)
    try:
        results = search.to_arrow()
    except Exception as e:
        logger.warning("Vector search failed: %s", e)
        return {}

    out = {}
    for i in range(len(results)):
        row = {col: results.column(col)[i].as_py() for col in results.column_names if col != "vector"}
        cosine_dist = row.pop("_distance", 0.0)
        row["vector_score"] = max(0.0, 1.0 - cosine_dist)  # cosine sim
        row["bm25_score"] = 0.0
        out[row["id"]] = row
    return out


def _fts_search(table, query_text: str, pool_size: int, where: str) -> dict[str, dict]:
    """Run BM25 full-text search, return {id: {row_data + bm25_score}}."""
    search = table.search(query_text, query_type="fts").limit(pool_size)
    if where:
        search = search.where(where)
    try:
        results = search.to_arrow()
    except Exception as e:
        logger.debug("FTS search failed (index may not exist): %s", e)
        return {}

    out = {}
    for i in range(len(results)):
        row = {col: results.column(col)[i].as_py() for col in results.column_names if col != "vector"}
        bm25 = row.pop("_score", 0.0)
        row["bm25_score"] = bm25
        row["vector_score"] = 0.0
        out[row["id"]] = row
    return out


def _fuse(
    vector_hits: dict[str, dict],
    fts_hits: dict[str, dict],
) -> dict[str, dict]:
    """Merge vector and FTS results with weighted-sum fusion + BM25 exact-match floor.

    fused = max(
        VECTOR_WEIGHT * vector_score + BM25_WEIGHT * bm25_score,
        bm25_score * BM25_FLOOR_FACTOR  if bm25_score >= BM25_EXACT_FLOOR  else 0
    )
    clamped to [SCORE_CLAMP_MIN, 1.0]
    """
    # Union all IDs
    all_ids = set(vector_hits) | set(fts_hits)
    merged: dict[str, dict] = {}

    for mid in all_ids:
        v = vector_hits.get(mid, {})
        f = fts_hits.get(mid, {})

        # Take row data from whichever source has it (prefer vector for metadata)
        row = {**f, **v} if v else {**v, **f}

        vs = v.get("vector_score", 0.0)
        bs = f.get("bm25_score", 0.0)

        weighted = VECTOR_WEIGHT * vs + BM25_WEIGHT * bs
        bm25_floor = bs * BM25_FLOOR_FACTOR if bs >= BM25_EXACT_FLOOR else 0.0
        fused = max(weighted, bm25_floor)
        fused = min(1.0, max(SCORE_CLAMP_MIN, fused))

        row["vector_score"] = vs
        row["bm25_score"] = bs
        row["fused_score"] = fused
        merged[mid] = row

    return merged


def _to_decayable(row: dict) -> DecayableMemory:
    """Build a DecayableMemory from a search result row."""
    return DecayableMemory(
        importance=row.get("importance", 5),
        confidence=row.get("confidence", 1.0),
        tier=row.get("tier", "working"),
        temporal_type=row.get("temporal_type", "static"),
        access_count=row.get("access_count", 0),
        created_at=row.get("created_at", 0.0),
        last_accessed_at=row.get("last_accessed_at", 0.0),
    )


def hybrid_recall(
    table,
    query_text: str,
    query_vector: list[float],
    limit: int = 5,
    where: str = "",
    apply_decay: bool = True,
    apply_rerank: bool = False,
    now: float | None = None,
) -> list[ScoredMemory]:
    """Run hybrid retrieval: vector + BM25 fusion + optional rerank + decay.

    1. Fetch candidate_pool = max(20, limit*2) from each of vector and FTS
    2. Fuse with weighted sum + BM25 exact-match floor
    3. Rerank top limit*2 via LLM scoring (if apply_rerank and config enabled)
    4. Apply decay-engine search boost (if apply_decay)
    5. Drop below HARD_MIN_SCORE
    6. Return top `limit` results sorted by final score desc
    """
    if now is None:
        now = time.time()

    pool_size = max(20, limit * 2)

    # Parallel-ish searches (both hit LanceDB, but Python is single-threaded)
    vector_hits = _vector_search(table, query_vector, pool_size, where)
    fts_hits = _fts_search(table, query_text, pool_size, where)

    if not vector_hits and not fts_hits:
        return []

    # Fuse
    merged = _fuse(vector_hits, fts_hits)

    # Optional reranking (LLM-based, only on explicit recall, not hook path)
    if apply_rerank and config.RERANK_ENABLED and merged:
        from .reranker import rerank as _rerank
        # Sort by fused score, take top limit*2 for reranking
        sorted_candidates = sorted(merged.values(), key=lambda r: r["fused_score"], reverse=True)
        rerank_pool = sorted_candidates[:limit * 2]
        reranked = _rerank(query_text, rerank_pool)
        # Rebuild merged dict with updated fused scores
        for row in reranked:
            mid = row.get("id")
            if mid and mid in merged:
                merged[mid]["fused_score"] = row["fused_score"]
                merged[mid]["rerank_score"] = row.get("rerank_score")

    # Apply decay boost
    results = []
    for mid, row in merged.items():
        fused = row["fused_score"]

        if apply_decay:
            mem = _to_decayable(row)
            final_score = apply_search_boost(fused, mem, now)
        else:
            final_score = fused

        if final_score < HARD_MIN_SCORE:
            continue

        results.append(ScoredMemory(
            id=mid,
            content=row.get("content", ""),
            abstract=row.get("abstract", ""),
            category=row.get("category", ""),
            project=row.get("project", ""),
            tags=row.get("tags", "[]"),
            importance=row.get("importance", 5),
            tier=row.get("tier", "working"),
            scope=row.get("scope", "global"),
            confidence=row.get("confidence", 1.0),
            score=final_score,
            vector_score=row["vector_score"],
            bm25_score=row["bm25_score"],
        ))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]
