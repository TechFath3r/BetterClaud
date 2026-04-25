<div align="center">

# 🦞 OpenClawdCode

**Give Claude Code the memory and context engine OpenClaw users loved — locally, via MCP.**

[![Claude Code](https://img.shields.io/badge/Claude_Code-MCP-blue)](https://docs.anthropic.com/en/docs/claude-code)
[![LanceDB](https://img.shields.io/badge/LanceDB-Vector_Store-orange)](https://lancedb.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status: Early / Community Welcome](https://img.shields.io/badge/Status-Early-yellow.svg)](#contributing)

</div>

---

## Why this exists

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) is powerful. But it forgets everything between sessions, and when its context window fills up, older messages are lost.

The OpenClaw community built two plugins that fixed this for that agent:

- **[memory-lancedb-pro](https://github.com/CortexReach/memory-lancedb-pro)** — auto-captured long-term memory with hybrid retrieval, cross-encoder rerank, Weibull decay, and per-scope isolation
- **[lossless-claw](https://github.com/Martian-Engineering/lossless-claw)** — LCM (Lossless Context Management): every message preserved in a SQLite DAG of summaries, with tools to drill back into raw detail on demand

**OpenClawdCode is an attempt to bring those same capabilities to Claude Code.** Not a fork, not a replacement — a spiritual port, re-implemented as an MCP server plus Claude Code hooks. Everything runs locally on one machine. No cloud, no server daemon, no telemetry.

## What it does (and honestly, what it can't)

### It can

- **Persistent memory across sessions and projects** — LanceDB-backed, semantic + BM25 hybrid retrieval, auto-capture from conversations via hooks
- **Automatic context injection** — relevant memories surface before each prompt via the `UserPromptSubmit` hook (no manual recall needed)
- **Per-project / per-scope isolation** — memories tagged and filtered by working directory, project, or custom scope
- **Obsidian vault integration** — index your notes for semantic search, write session logs back into the vault
- **Lossless message log** *(planned v1.1)* — every turn archived to SQLite with a DAG of summaries; agent can drill back into any compacted history via `lcm_grep` / `lcm_expand` style tools
- **Intelligent forgetting** *(planned v1)* — Weibull-decay scoring so noise fades and important memories stay

### It can't

Claude Code owns its own context engine — we can **augment** it (inject context, provide recall tools, archive messages) but we **can't replace** its native compaction the way `lossless-claw` replaces OpenClaw's. In practice: nothing is ever truly lost because we archive everything ourselves, and the agent can always pull it back. But Claude Code will still compact natively when it hits the limit. See [the honest trade-offs](#honest-trade-offs) below.

## How it works

```
┌─────────────────────────────────────────────────────────────┐
│                     Claude Code session                      │
└───────┬──────────────────────────────────┬──────────────────┘
        │                                   │
    Hooks (settings.json)              MCP tools
        │                                   │
        ├─ UserPromptSubmit → inject   ├─ store_memory
        │  ranked memories              ├─ recall_memory
        ├─ PostToolUse → log turn       ├─ search_vault
        ├─ Stop → extract + summarize   ├─ log_session
        ├─ PostCompact → flag recall    └─ (lcm_* tools v1.1)
        └─ SessionStart → preload
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│   LanceDB (memories, vector + BM25)  │  SQLite (message DAG)│
│   Ollama (embeddings + extraction)   │  Obsidian (sessions) │
└─────────────────────────────────────────────────────────────┘
```

Everything is local. Ollama runs embeddings (`nomic-embed-text`) and optionally the memory extractor. LanceDB stores memories. SQLite will store the lossless message log. Your Obsidian vault (if configured) is both a searchable knowledge source and the destination for session logs.

## Quick Start

```bash
git clone https://github.com/TechFath3r/OpenClawdCode.git
cd OpenClawdCode
./setup.sh
```

The setup script:
1. Installs Ollama and pulls the embedding model
2. Creates a Python venv and installs the package
3. Registers the MCP server with Claude Code (`claude mcp add`)
4. Wires `UserPromptSubmit`, `Stop`, and `PostCompact` hooks into `~/.claude/settings.json`
5. Optionally sets up Obsidian vault integration

**Requirements:** Python 3.10+, Claude Code CLI, Ollama (auto-installed), ~500MB disk.

## Tools Provided to Claude

| Tool | Description | Status |
|------|-------------|--------|
| `store_memory` | Save facts, learnings, preferences, decisions | ✅ |
| `recall_memory` | Hybrid vector + BM25 search with decay scoring | ✅ |
| `extract_memories` | Auto-extract memories from conversation (with dedup) | ✅ |
| `log_session` | Write session summary as markdown | ✅ |
| `search_vault` | Search indexed Obsidian vault | ✅ (optional) |
| `search_knowledge` | Search ChromaDB knowledge bases | ✅ (optional) |
| `load_context` | Load context profile for current use case | ✅ (optional) |
| `lcm_grep` / `lcm_expand` / `lcm_describe` | Search and drill into compacted message history | 🚧 v1.1 |

## Configuration

All settings via environment variables in `~/.config/openclawd/.env`. Copy from [`.env.example`](.env.example).

| Variable | Default | Description |
|---|---|---|
| `OPENCLAWD_LANCEDB_PATH` | `~/.local/share/openclawd/lancedb` | LanceDB directory |
| `OPENCLAWD_OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint |
| `OPENCLAWD_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `OPENCLAWD_VAULT_PATH` | *(empty)* | Obsidian vault path |
| `OPENCLAWD_CHROMADB_PATH` | *(empty)* | ChromaDB directory |
| `OPENCLAWD_CONTEXT_DIR` | *(empty)* | Context profiles directory |

## Obsidian Vault Integration

```bash
# Full index
openclawd-index --vault /path/to/vault

# Incremental (only changed files)
openclawd-index --incremental

# Cron it (every 15 min)
# */15 * * * * ~/.local/share/openclawd/venv/bin/openclawd-index --incremental
```

Session logs land in `{vault}/Claude/sessions/` — visible on any device syncing your vault.

## Migration from memory-lancedb-pro

If you're coming from OpenClaw's `memory-lancedb-pro`, there's a migration script that reads your existing LanceDB memories and imports them into OpenClawdCode's schema:

```bash
python3 scripts/migrate_claudia.py --source /path/to/existing/lancedb --table memories
```

*(Migration is best-effort — schemas differ slightly. Review with `--dry-run` first.)*

## Honest Trade-offs

Compared to running OpenClaw + both plugins:

**What you lose:**
- **Messaging channels.** OpenClaw's whole thing is "ask me on WhatsApp/Slack/Discord." Claude Code is a terminal. If you want channels, keep OpenClaw for that — OpenClawdCode is for in-terminal dev work.
- **Truly lossless context.** Claude Code will still compact natively. We archive everything to SQLite, so nothing is *actually* lost, and the agent can pull back any raw message via `lcm_expand`-style tools. But we can't prevent the compaction itself the way `lossless-claw` does inside OpenClaw.
- **Per-skill plugin isolation the OpenClaw way.** Claude Code's skill model is different — simpler, but less pluggable.

**What you gain:**
- Lives inside the tool you're already using every day for code
- Direct Obsidian integration without extra plumbing
- Not coupled to any single agent's plugin API stability

## Contributing

**This project exists because the OpenClaw community lost two plugins they relied on.** If you came from there and miss those capabilities, your input is the most valuable thing we can get:

- What did you rely on `memory-lancedb-pro` for that isn't captured here?
- What `lossless-claw` feature do you miss the most?
- What doesn't work on your setup?

Open an issue, start a discussion, or send a PR. Early and rough is fine — this is a community port, not a product.

**Roadmap lives in [`tasks/todo.md`](tasks/todo.md).** Pick anything unclaimed.

## Credits

Heavily inspired by:
- **[CortexReach/memory-lancedb-pro](https://github.com/CortexReach/memory-lancedb-pro)** — the memory architecture, auto-capture, Weibull decay, hybrid retrieval
- **[Martian-Engineering/lossless-claw](https://github.com/Martian-Engineering/lossless-claw)** — the LCM DAG approach and recall tools
- **[OpenClaw](https://github.com/openclaw/openclaw)** — the agent those plugins were built for, and the community that built them

This project is not affiliated with OpenClaw, CortexReach, or Martian Engineering. It's an independent re-implementation of the same ideas for a different host agent.

## License

MIT
