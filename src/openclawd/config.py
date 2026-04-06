"""Configuration from environment variables with sensible defaults."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from config dir if it exists
_env_file = Path.home() / ".config" / "openclawd" / ".env"
if _env_file.exists():
    load_dotenv(_env_file)


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _get_path(key: str, default: str = "") -> str:
    val = _get(key, default)
    return str(Path(val).expanduser()) if val else ""


# LanceDB
LANCEDB_PATH: str = _get_path("OPENCLAWD_LANCEDB_PATH", "~/.local/share/openclawd/lancedb")

# Ollama
OLLAMA_URL: str = _get("OPENCLAWD_OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL: str = _get("OPENCLAWD_EMBED_MODEL", "nomic-embed-text")
EMBED_DIM: int = int(_get("OPENCLAWD_EMBED_DIM", "768"))

# Obsidian vault (empty = disabled)
VAULT_PATH: str = _get_path("OPENCLAWD_VAULT_PATH", "")
VAULT_SESSION_DIR: str = _get("OPENCLAWD_VAULT_SESSION_DIR", "Claude/sessions")

# Table names
MEMORY_TABLE: str = _get("OPENCLAWD_MEMORY_TABLE", "memories")
VAULT_TABLE: str = _get("OPENCLAWD_VAULT_TABLE", "obsidian_vault")

# ChromaDB (empty = disabled)
CHROMADB_PATH: str = _get_path("OPENCLAWD_CHROMADB_PATH", "")
CHROMADB_COLLECTION: str = _get("OPENCLAWD_CHROMADB_COLLECTION", "default")

# Context profiles directory (empty = disabled)
CONTEXT_DIR: str = _get_path("OPENCLAWD_CONTEXT_DIR", "")

# Memory extraction LLM
# "haiku" uses Anthropic API (needs ANTHROPIC_API_KEY), "ollama" uses local Ollama.
# "auto" (default) → haiku if ANTHROPIC_API_KEY is set, else ollama.
EXTRACTOR: str = _get("OPENCLAWD_EXTRACTOR", "auto")
EXTRACTOR_OLLAMA_MODEL: str = _get("OPENCLAWD_EXTRACTOR_MODEL", "llama3.2")
EXTRACTOR_MAX_MEMORIES: int = int(_get("OPENCLAWD_EXTRACTOR_MAX_MEMORIES", "5"))

# Reranking (opt-in — adds latency, one LLM call per candidate)
RERANK_ENABLED: bool = _get("OPENCLAWD_RERANK", "false").lower() in ("true", "1", "yes")
RERANK_MODEL: str = _get("OPENCLAWD_RERANK_MODEL", "")  # empty = use EXTRACTOR_OLLAMA_MODEL
RERANK_BLEND: float = float(_get("OPENCLAWD_RERANK_BLEND", "0.6"))  # rerank weight in blend
