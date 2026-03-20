"""Configuration from environment variables with sensible defaults."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from config dir if it exists
_env_file = Path.home() / ".config" / "betterclaud" / ".env"
if _env_file.exists():
    load_dotenv(_env_file)


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _get_path(key: str, default: str = "") -> str:
    val = _get(key, default)
    return str(Path(val).expanduser()) if val else ""


# LanceDB
LANCEDB_PATH: str = _get_path("BETTERCLAUD_LANCEDB_PATH", "~/.local/share/betterclaud/lancedb")

# Ollama
OLLAMA_URL: str = _get("BETTERCLAUD_OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL: str = _get("BETTERCLAUD_EMBED_MODEL", "nomic-embed-text")
EMBED_DIM: int = int(_get("BETTERCLAUD_EMBED_DIM", "768"))

# Obsidian vault (empty = disabled)
VAULT_PATH: str = _get_path("BETTERCLAUD_VAULT_PATH", "")
VAULT_SESSION_DIR: str = _get("BETTERCLAUD_VAULT_SESSION_DIR", "Claude/sessions")

# Table names
MEMORY_TABLE: str = _get("BETTERCLAUD_MEMORY_TABLE", "memories")
VAULT_TABLE: str = _get("BETTERCLAUD_VAULT_TABLE", "obsidian_vault")

# ChromaDB (empty = disabled)
CHROMADB_PATH: str = _get_path("BETTERCLAUD_CHROMADB_PATH", "")
CHROMADB_COLLECTION: str = _get("BETTERCLAUD_CHROMADB_COLLECTION", "default")

# Context profiles directory (empty = disabled)
CONTEXT_DIR: str = _get_path("BETTERCLAUD_CONTEXT_DIR", "")
