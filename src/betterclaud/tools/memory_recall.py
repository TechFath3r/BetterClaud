"""MCP tool: recall memories via semantic search."""

import json

from ..db import MEMORY_SCHEMA, get_or_create_table
from ..embeddings import embed_one
from .. import config


def memory_recall(
    query: str,
    limit: int = 5,
    category: str = "",
    project: str = "",
    min_importance: int = 1,
) -> str:
    """Search stored memories semantically.

    Args:
        query: Natural language search query.
        limit: Max number of results (default 5).
        category: Filter by category (empty = all).
        project: Filter by project (empty = all).
        min_importance: Minimum importance threshold (default 1).
    """
    table = get_or_create_table(config.MEMORY_TABLE, MEMORY_SCHEMA)

    try:
        if table.count_rows() == 0:
            return "No memories stored yet."
    except Exception:
        return "No memories stored yet."

    vector = embed_one(query)

    search = table.search(vector).limit(limit)

    # Build where clause
    filters = []
    if category:
        filters.append(f"category = '{category}'")
    if project:
        filters.append(f"project = '{project}'")
    if min_importance > 1:
        filters.append(f"importance >= {min_importance}")

    if filters:
        search = search.where(" AND ".join(filters))

    try:
        results = search.to_arrow()
    except Exception as e:
        return f"Search error: {e}"

    if len(results) == 0:
        return "No matching memories found."

    output = []
    for i in range(len(results)):
        content = results.column("content")[i].as_py()
        cat = results.column("category")[i].as_py()
        proj = results.column("project")[i].as_py()
        tags = results.column("tags")[i].as_py()
        imp = results.column("importance")[i].as_py()
        dist = results.column("_distance")[i].as_py()

        tags_str = ", ".join(json.loads(tags)) if tags else ""
        proj_str = f" [{proj}]" if proj else ""
        tags_line = f"  Tags: {tags_str}\n" if tags_str else ""

        output.append(
            f"--- Memory {i + 1} (distance: {dist:.4f}) ---\n"
            f"  Category: {cat}{proj_str} | Importance: {imp}\n"
            f"{tags_line}"
            f"  {content}"
        )

    return "\n\n".join(output)
