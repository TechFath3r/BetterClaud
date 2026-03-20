# BetterClaud

Persistent cross-project memory for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) via MCP.

Claude Code is powerful but forgets everything between sessions. BetterClaud gives it a long-term memory using semantic vector search — memories persist across sessions and projects.

## How It Works

- **MCP server** provides memory tools to Claude Code (store, recall, search)
- **LanceDB** stores memories as embeddings locally (no cloud, no server daemon)
- **Ollama** generates embeddings locally via `nomic-embed-text`
- **Obsidian vault** integration for searching notes and writing session logs (optional)
- **ChromaDB** integration for domain-specific knowledge bases (optional)
- **Context profiles** for per-channel/per-use-case instructions (optional)

Everything runs locally on one machine.

## Quick Start

```bash
git clone https://github.com/yourusername/betterclaud.git
cd betterclaud
./setup.sh
```

The setup script:
1. Installs Ollama and pulls the embedding model
2. Creates a Python venv and installs the package
3. Registers the MCP server with Claude Code
4. Configures session hooks
5. Optionally sets up Obsidian vault integration

## Tools Provided to Claude

| Tool | Description |
|------|-------------|
| `store_memory` | Save facts, learnings, preferences, decisions |
| `recall_memory` | Semantic search over stored memories |
| `log_session` | Write session summary as markdown |
| `search_vault` | Search indexed Obsidian vault (if configured) |
| `search_knowledge` | Search ChromaDB knowledge bases (if configured) |
| `load_context` | Load context profile for current use case (if configured) |

## Configuration

All settings are via environment variables. Edit `~/.config/betterclaud/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `BETTERCLAUD_LANCEDB_PATH` | `~/.local/share/betterclaud/lancedb` | LanceDB directory |
| `BETTERCLAUD_OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint |
| `BETTERCLAUD_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `BETTERCLAUD_VAULT_PATH` | *(empty)* | Obsidian vault path |
| `BETTERCLAUD_CHROMADB_PATH` | *(empty)* | ChromaDB directory |
| `BETTERCLAUD_CONTEXT_DIR` | *(empty)* | Context profiles directory |

See `.env.example` for all options.

## Obsidian Vault Integration

To index your vault for semantic search:

```bash
# Full index
betterclaud-index --vault /path/to/vault

# Incremental (only changed files)
betterclaud-index --incremental

# Set up a cron job for auto-indexing
# */15 * * * * ~/.local/share/betterclaud/venv/bin/betterclaud-index --incremental
```

Session logs are written to `{vault}/Claude/sessions/` — visible on all devices via Syncthing.

## Context Profiles

Create `.md` files in your context directory (e.g., inside your Obsidian vault):

```
contexts/
├── casual.md    # Light chat
├── dev.md       # Software development
├── repair.md    # Electronics repair
└── sysadmin.md  # Infrastructure
```

Each file contains instructions that Claude follows when the profile is loaded.

## Backup

The only data that needs backing up is `~/.local/share/betterclaud/lancedb/` — your memories database. Everything else is either in the repo (code), in your Obsidian vault (synced), or trivially recreatable (config).

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

MIT
