"""Cross-encoder-style reranker using Ollama LLM scoring.

Since Ollama doesn't support dedicated cross-encoder models, we use the
chat endpoint to ask a model to rate query-document relevance on [0, 1].
This is slower than a true cross-encoder but works with any Ollama model.

The reranker blends its score with the existing fused score:
  final = RERANK_BLEND * rerank_score + (1 - RERANK_BLEND) * fused_score

Opt-in via OPENCLAWD_RERANK=true. Not used on the hook path (too slow).

Reference: references/source-algorithms.md § Cross-encoder reranker
"""

from __future__ import annotations

import logging
import re

import httpx

from . import config

logger = logging.getLogger("openclawd")

RERANK_SYSTEM = (
    "You are a relevance scoring engine. Given a search query and a memory, "
    "rate how relevant the memory is to the query. Output ONLY a decimal "
    "number between 0.0 (completely irrelevant) and 1.0 (perfectly relevant). "
    "No explanation, no text, just the number."
)

RERANK_USER_TEMPLATE = "Query: {query}\n\nMemory: {content}\n\nRelevance score:"


def _score_one(query: str, content: str) -> float | None:
    """Ask Ollama to score one query-document pair. Returns float or None on failure."""
    model = config.RERANK_MODEL or config.EXTRACTOR_OLLAMA_MODEL
    try:
        resp = httpx.post(
            f"{config.OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": RERANK_SYSTEM},
                    {"role": "user", "content": RERANK_USER_TEMPLATE.format(
                        query=query[:500], content=content[:500]
                    )},
                ],
                "stream": False,
            },
            timeout=30,
        )
        resp.raise_for_status()
        text = resp.json()["message"]["content"].strip()
        # Extract first float-like pattern
        match = re.search(r"(\d+\.?\d*)", text)
        if match:
            score = float(match.group(1))
            return min(1.0, max(0.0, score))
    except Exception as e:
        logger.debug("Rerank scoring failed for one candidate: %s", e)
    return None


def rerank(
    query: str,
    candidates: list[dict],
    fused_score_key: str = "fused_score",
) -> list[dict]:
    """Rerank candidates by LLM relevance scoring.

    For each candidate, calls Ollama to score query-document relevance,
    then blends: final = blend * rerank_score + (1-blend) * fused_score.
    Candidates that fail scoring keep their original fused_score.

    Args:
        query: The search query text.
        candidates: List of dicts, each must have `fused_score_key` and `content`.
        fused_score_key: Key name for the existing fused score.

    Returns:
        Same list with `rerank_score` and updated `fused_score` keys, sorted desc.
    """
    blend = config.RERANK_BLEND

    for cand in candidates:
        score = _score_one(query, cand.get("content", ""))
        if score is not None:
            cand["rerank_score"] = score
            original = cand.get(fused_score_key, 0.5)
            cand[fused_score_key] = blend * score + (1 - blend) * original
        else:
            cand["rerank_score"] = None

    candidates.sort(key=lambda c: c.get(fused_score_key, 0), reverse=True)
    return candidates
