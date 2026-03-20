"""MCP tool: store a memory."""

import hashlib
import json
import time

from ..db import MEMORY_SCHEMA, get_or_create_table
from ..embeddings import embed_one
from .. import config

VALID_CATEGORIES = {
    "general", "preference", "decision", "learning",
    "architecture", "debugging", "tool_usage",
}


def memory_store(
    content: str,
    category: str = "general",
    project: str = "",
    tags: list[str] | None = None,
    importance: int = 5,
) -> str:
    """Store a memory for later recall. Deduplicates by content hash.

    Args:
        content: The memory text to store.
        category: One of: general, preference, decision, learning, architecture, debugging, tool_usage.
        project: Project scope (empty string = cross-project).
        tags: Optional list of tags.
        importance: 1-10 importance rating (default 5).
    """
    if tags is None:
        tags = []

    if category not in VALID_CATEGORIES:
        return f"Invalid category '{category}'. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"

    importance = max(1, min(10, importance))

    # Deterministic ID from content
    mem_id = hashlib.sha256(content.encode()).hexdigest()[:16]
    now = time.time()

    vector = embed_one(content)

    table = get_or_create_table(config.MEMORY_TABLE, MEMORY_SCHEMA)

    # Check if exists — if so, update
    try:
        existing = table.search().where(f"id = '{mem_id}'").limit(1).to_arrow()
        if len(existing) > 0:
            table.delete(f"id = '{mem_id}'")
    except Exception:
        pass

    table.add([{
        "id": mem_id,
        "content": content,
        "vector": vector,
        "category": category,
        "project": project,
        "tags": json.dumps(tags),
        "importance": importance,
        "created_at": now,
        "updated_at": now,
        "source": "manual",
    }])

    return f"Memory stored (id={mem_id}, category={category}, importance={importance})"
