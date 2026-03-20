"""MCP tool: search Obsidian vault via semantic search."""

from ..db import VAULT_SCHEMA, get_or_create_table
from ..embeddings import embed_one
from .. import config


def vault_search(query: str, limit: int = 5) -> str:
    """Search the indexed Obsidian vault semantically.

    Args:
        query: Natural language search query.
        limit: Max number of results (default 5).
    """
    table = get_or_create_table(config.VAULT_TABLE, VAULT_SCHEMA)

    try:
        if table.count_rows() == 0:
            return "Vault index is empty. Run 'betterclaud-index' to index your vault."
    except Exception:
        return "Vault index is empty. Run 'betterclaud-index' to index your vault."

    vector = embed_one(query)

    try:
        results = table.search(vector).limit(limit).to_arrow()
    except Exception as e:
        return f"Search error: {e}"

    if len(results) == 0:
        return "No matching vault content found."

    output = []
    for i in range(len(results)):
        filepath = results.column("filepath")[i].as_py()
        heading = results.column("heading")[i].as_py()
        text = results.column("text")[i].as_py()
        dist = results.column("_distance")[i].as_py()

        preview = text[:500] + ("..." if len(text) > 500 else "")
        output.append(
            f"--- Result {i + 1} (distance: {dist:.4f}) ---\n"
            f"  File: {filepath}\n"
            f"  Section: {heading}\n"
            f"  {preview}"
        )

    return "\n\n".join(output)
