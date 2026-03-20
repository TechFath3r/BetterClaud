"""Ollama embedding client."""

import httpx

from . import config


def _url() -> str:
    return f"{config.OLLAMA_URL}/api/embed"


def embed_one(text: str) -> list[float]:
    """Get embedding for a single text."""
    resp = httpx.post(
        _url(),
        json={"model": config.EMBED_MODEL, "input": [text]},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"][0]


def embed_batch(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """Get embeddings for multiple texts in batches."""
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = httpx.post(
            _url(),
            json={"model": config.EMBED_MODEL, "input": batch},
            timeout=120,
        )
        resp.raise_for_status()
        all_embeddings.extend(resp.json()["embeddings"])
    return all_embeddings
