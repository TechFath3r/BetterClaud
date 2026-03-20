"""BetterClaud MCP server — persistent memory for Claude Code."""

import logging

from mcp.server.fastmcp import FastMCP

from . import config
from .tools.memory_store import memory_store
from .tools.memory_recall import memory_recall
from .tools.session_log import session_log

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("betterclaud")

mcp = FastMCP("betterclaud-memory")

# --- Always-on tools ---

@mcp.tool()
def store_memory(
    content: str,
    category: str = "general",
    project: str = "",
    tags: list[str] | None = None,
    importance: int = 5,
) -> str:
    """Store a memory for later recall across sessions and projects.

    Categories: general, preference, decision, learning, architecture, debugging, tool_usage.
    """
    return memory_store(content, category, project, tags, importance)


@mcp.tool()
def recall_memory(
    query: str,
    limit: int = 5,
    category: str = "",
    project: str = "",
    min_importance: int = 1,
) -> str:
    """Search stored memories semantically. Use at session start and when context is needed."""
    return memory_recall(query, limit, category, project, min_importance)


@mcp.tool()
def log_session(
    summary: str,
    project: str = "general",
    title: str = "",
) -> str:
    """Write a session summary as a markdown log file."""
    return session_log(summary, project, title)


# --- Conditional tools ---

if config.VAULT_PATH:
    from .tools.vault_search import vault_search

    @mcp.tool()
    def search_vault(query: str, limit: int = 5) -> str:
        """Search the indexed Obsidian vault semantically."""
        return vault_search(query, limit)

    logger.info("Vault search enabled (path: %s)", config.VAULT_PATH)


if config.CHROMADB_PATH:
    try:
        import chromadb as _  # noqa: F811

        from .tools.knowledge_search import knowledge_search

        @mcp.tool()
        def search_knowledge(query: str, collection: str = "", limit: int = 5) -> str:
            """Search a ChromaDB knowledge base for domain-specific information."""
            return knowledge_search(query, collection, limit)

        logger.info("Knowledge search enabled (path: %s)", config.CHROMADB_PATH)
    except ImportError:
        logger.warning(
            "BETTERCLAUD_CHROMADB_PATH is set but chromadb is not installed. "
            "Install with: pip install betterclaud[chromadb]"
        )


if config.CONTEXT_DIR:
    from .tools.load_context import load_context as _load_context

    @mcp.tool()
    def load_context(profile: str) -> str:
        """Load a context profile with instructions for a specific use case (e.g. 'repair', 'dev', 'casual')."""
        return _load_context(profile)

    logger.info("Context profiles enabled (dir: %s)", config.CONTEXT_DIR)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
