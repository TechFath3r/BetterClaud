"""MCP tool: recall memories via hybrid semantic + keyword search."""

import json

from ..db import MEMORY_SCHEMA, get_or_create_table
from ..embeddings import embed_one
from ..retriever import hybrid_recall, _ensure_fts_index
from .. import config


def memory_recall(
    query: str,
    limit: int = 5,
    category: str = "",
    project: str = "",
    min_importance: int = 1,
    tier: str = "",
    scope: str = "",
) -> str:
    """Search stored memories using hybrid vector + BM25 retrieval with decay scoring.

    Args:
        query: Natural language search query.
        limit: Max number of results (default 5).
        category: Filter by category (empty = all).
        project: Filter by project (empty = all).
        min_importance: Minimum importance threshold (default 1).
        tier: Filter by tier: core|working|peripheral (empty = all).
        scope: Filter by scope string (empty = all).
    """
    table = get_or_create_table(config.MEMORY_TABLE, MEMORY_SCHEMA)

    try:
        if table.count_rows() == 0:
            return "No memories stored yet."
    except Exception:
        return "No memories stored yet."

    # Ensure FTS index exists for BM25 leg of hybrid search
    _ensure_fts_index(table)

    vector = embed_one(query)

    # Build where clause
    filters = []
    if category:
        filters.append(f"category = '{category}'")
    if project:
        filters.append(f"project = '{project}'")
    if min_importance > 1:
        filters.append(f"importance >= {min_importance}")
    if tier:
        filters.append(f"tier = '{tier}'")
    if scope:
        filters.append(f"scope = '{scope}'")

    where = " AND ".join(filters) if filters else ""

    results = hybrid_recall(
        table=table,
        query_text=query,
        query_vector=vector,
        limit=limit,
        where=where,
        apply_decay=True,
        apply_rerank=True,  # explicit tool call — rerank if enabled
    )

    if not results:
        return "No matching memories found."

    output = []
    for i, mem in enumerate(results):
        tags_str = ", ".join(json.loads(mem.tags)) if mem.tags and mem.tags != "[]" else ""
        proj_str = f" [{mem.project}]" if mem.project else ""
        tags_line = f"  Tags: {tags_str}\n" if tags_str else ""

        output.append(
            f"--- Memory {i + 1} (score: {mem.score:.4f} | vec: {mem.vector_score:.3f} bm25: {mem.bm25_score:.3f}) ---\n"
            f"  Category: {mem.category}{proj_str} | Importance: {mem.importance} | Tier: {mem.tier} | Scope: {mem.scope}\n"
            f"{tags_line}"
            f"  {mem.content}"
        )

    return "\n\n".join(output)
