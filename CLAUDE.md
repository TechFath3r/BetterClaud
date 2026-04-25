# CLAUDE.md

Always-on essentials for every task. Supporting docs live in `claude/`.

## Project

**OpenClawdCode** — persistent memory + context engine for [Claude Code](https://docs.anthropic.com/en/docs/claude-code), delivered as an MCP server plus hooks. Spiritual port of OpenClaw's `memory-lancedb-pro` and `lossless-claw` plugins. Local-only (LanceDB + Ollama + SQLite). See `README.md` for the full vision.

## What to read

| Task type | Read |
|---|---|
| Any task | This file (always loaded) + `claude/workflow.md` |
| Writing or modifying code | + `claude/conventions.md` |
| Touching architecture, schemas, hooks, or MCP surface | + `claude/context.md` |

## Repo Layout

```
OpenClawdCode/
├── src/openclawd/          ← Python package
│   ├── server.py           ← MCP server (FastMCP, stdio transport)
│   ├── config.py           ← Env-var config
│   ├── db.py               ← LanceDB connection + schemas
│   ├── embeddings.py       ← Ollama embedding client
│   ├── vault_indexer.py    ← Obsidian indexing logic
│   └── tools/              ← One file per MCP tool
├── hooks/                  ← Claude Code hooks (Stop, PostCompact, ...)
├── scripts/                ← CLI entry points (openclawd-index, migrate_*)
├── tests/                  ← pytest
├── claude/                 ← Supporting CLAUDE.md docs
├── tasks/                  ← todo.md, lessons.md
├── setup.sh                ← One-command installer
└── pyproject.toml
```

## Build & Development Commands

```bash
# Dev install (editable)
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Tests
pytest

# Run the MCP server directly (for debugging)
python3 -m openclawd.server

# Re-run full setup (idempotent)
./setup.sh
```

## Key Rules

1. **Plan first, build clean** — see `claude/workflow.md`
2. **Never mark a task complete without proving it works** (tests pass, types clean)
3. **Don't push to `main` unless explicitly asked** — commit locally, then wait
4. **Don't expand scope** — bug fixes don't need surrounding cleanup
5. **Record lessons** — after any correction, append to `tasks/lessons.md`

## Owner

Dan Starr (TechFath3r) — direct communicator, wants why before how. Prefers audit before action.

## Community-Facing Project

This is a public community port for OpenClaw refugees. When writing docs, commit messages, or README content, remember the audience is people who lost tools they relied on. Tone: honest about trade-offs, welcoming to contributors, no marketing fluff.
