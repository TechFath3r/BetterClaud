"""MCP tool: search ChromaDB knowledge bases (optional)."""

from .. import config


def _get_chromadb_collection(collection_name: str | None = None):
    """Get a ChromaDB collection, raising ImportError if chromadb isn't installed."""
    import chromadb

    client = chromadb.PersistentClient(path=config.CHROMADB_PATH)
    name = collection_name or config.CHROMADB_COLLECTION
    return client.get_collection(name)


def knowledge_search(
    query: str,
    collection: str = "",
    limit: int = 5,
) -> str:
    """Search a ChromaDB knowledge base.

    Args:
        query: Natural language search query.
        collection: ChromaDB collection name (empty = use default from config).
        limit: Max number of results (default 5).
    """
    try:
        col = _get_chromadb_collection(collection or None)
    except ImportError:
        return "ChromaDB is not installed. Install with: pip install betterclaud[chromadb]"
    except Exception as e:
        return f"Error accessing ChromaDB: {e}"

    try:
        results = col.query(query_texts=[query], n_results=limit)
    except Exception as e:
        return f"Search error: {e}"

    if not results["documents"] or not results["documents"][0]:
        return "No matching documents found."

    output = []
    docs = results["documents"][0]
    distances = results["distances"][0] if results.get("distances") else [None] * len(docs)
    metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)

    for i, (doc, dist, meta) in enumerate(zip(docs, distances, metadatas)):
        dist_str = f" (distance: {dist:.4f})" if dist is not None else ""
        meta_str = ""
        if meta:
            meta_parts = [f"{k}: {v}" for k, v in meta.items()]
            meta_str = f"  Metadata: {', '.join(meta_parts)}\n"

        preview = doc[:500] + ("..." if len(doc) > 500 else "")
        output.append(
            f"--- Result {i + 1}{dist_str} ---\n"
            f"{meta_str}"
            f"  {preview}"
        )

    return "\n\n".join(output)
