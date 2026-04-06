"""openclawd CLI — management and diagnostics.

Usage:
    openclawd doctor     Check installation health
    openclawd stats      Show memory statistics
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _check(label: str, fn) -> bool:
    """Run a check function, print result."""
    try:
        ok, detail = fn()
        status = "\033[32m✓\033[0m" if ok else "\033[31m✗\033[0m"
        print(f"  {status} {label}: {detail}")
        return ok
    except Exception as e:
        print(f"  \033[31m✗\033[0m {label}: {e}")
        return False


def cmd_doctor():
    """Run diagnostic checks on the OpenClawdCode installation."""
    from . import config

    print("OpenClawdCode Doctor\n")
    all_ok = True

    # 1. Ollama reachable
    def check_ollama():
        import httpx
        try:
            resp = httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=5)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return True, f"responding at {config.OLLAMA_URL} ({len(models)} models)"
        except Exception as e:
            return False, f"not reachable at {config.OLLAMA_URL} — {e}"
    all_ok &= _check("Ollama", check_ollama)

    # 2. Embedding model available
    def check_embed_model():
        import httpx
        resp = httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"].split(":")[0] for m in resp.json().get("models", [])]
        if config.EMBED_MODEL in models or config.EMBED_MODEL.split(":")[0] in models:
            return True, f"{config.EMBED_MODEL} available"
        return False, f"{config.EMBED_MODEL} not found — run: ollama pull {config.EMBED_MODEL}"
    all_ok &= _check("Embed model", check_embed_model)

    # 3. Embedding dimension
    def check_embed_dim():
        from .embeddings import embed_one
        vec = embed_one("test")
        if len(vec) == config.EMBED_DIM:
            return True, f"{len(vec)} dims (matches OPENCLAWD_EMBED_DIM)"
        return False, f"model returns {len(vec)} dims but OPENCLAWD_EMBED_DIM={config.EMBED_DIM}"
    all_ok &= _check("Embed dimension", check_embed_dim)

    # 4. LanceDB opens
    def check_lancedb():
        from .db import get_db
        db = get_db()
        tables = db.list_tables().tables
        return True, f"{len(tables)} tables at {config.LANCEDB_PATH}"
    all_ok &= _check("LanceDB", check_lancedb)

    # 5. Memory table exists
    def check_memory_table():
        from .db import get_db
        db = get_db()
        tables = db.list_tables().tables
        if config.MEMORY_TABLE in tables:
            from .db import get_or_create_table, MEMORY_SCHEMA
            table = get_or_create_table(config.MEMORY_TABLE, MEMORY_SCHEMA)
            return True, f"'{config.MEMORY_TABLE}' with {table.count_rows()} rows, {len(table.schema)} columns"
        return True, f"'{config.MEMORY_TABLE}' not yet created (will be on first store)"
    all_ok &= _check("Memory table", check_memory_table)

    # 6. Hooks in settings.json
    def check_hooks():
        settings_path = Path.home() / ".claude" / "settings.json"
        if not settings_path.exists():
            return False, f"{settings_path} not found"
        settings = json.loads(settings_path.read_text())
        hooks = settings.get("hooks", {})
        found = []
        for name in ["Stop", "PostCompact", "UserPromptSubmit", "SessionStart"]:
            if hooks.get(name):
                found.append(name)
        if len(found) >= 3:
            return True, f"hooks registered: {', '.join(found)}"
        return False, f"only {', '.join(found) or 'none'} — re-run ./setup.sh"
    all_ok &= _check("Claude Code hooks", check_hooks)

    # 7. MCP server registered
    def check_mcp():
        import subprocess
        try:
            result = subprocess.run(
                ["claude", "mcp", "list"], capture_output=True, text=True, timeout=10
            )
            if "openclawd-memory" in result.stdout:
                return True, "openclawd-memory registered"
            return False, "openclawd-memory not in 'claude mcp list' — re-run ./setup.sh"
        except FileNotFoundError:
            return False, "claude CLI not found"
        except Exception as e:
            return False, str(e)
    all_ok &= _check("MCP server", check_mcp)

    # 8. Extractor backend
    def check_extractor():
        backend = config.EXTRACTOR
        if backend == "auto":
            has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
            resolved = "haiku" if has_key else "ollama"
            return True, f"auto → {resolved} ({'API key found' if has_key else 'no API key, using Ollama'})"
        return True, f"explicit: {backend}"
    all_ok &= _check("Extractor LLM", check_extractor)

    # 9. Reranker
    def check_rerank():
        if config.RERANK_ENABLED:
            model = config.RERANK_MODEL or config.EXTRACTOR_OLLAMA_MODEL
            return True, f"enabled (model: {model}, blend: {config.RERANK_BLEND})"
        return True, "disabled (set OPENCLAWD_RERANK=true to enable)"
    all_ok &= _check("Reranker", check_rerank)

    print()
    if all_ok:
        print("\033[32mAll checks passed.\033[0m")
    else:
        print("\033[33mSome checks failed. Fix the issues above and re-run.\033[0m")

    return 0 if all_ok else 1


def cmd_stats():
    """Show memory store statistics."""
    from . import config
    from .db import get_db

    db = get_db()
    tables = db.list_tables().tables

    print("OpenClawdCode Stats\n")
    print(f"  LanceDB path: {config.LANCEDB_PATH}")
    print(f"  Tables: {', '.join(tables) or '(none)'}")

    if config.MEMORY_TABLE in tables:
        from .db import get_or_create_table, MEMORY_SCHEMA
        table = get_or_create_table(config.MEMORY_TABLE, MEMORY_SCHEMA)
        data = table.to_arrow()
        total = len(data)
        print(f"\n  Memories: {total}")

        if total > 0:
            # Category breakdown
            cats = {}
            tiers = {}
            sources = {}
            for i in range(total):
                cat = data.column("category")[i].as_py()
                cats[cat] = cats.get(cat, 0) + 1
                tier = data.column("tier")[i].as_py()
                tiers[tier] = tiers.get(tier, 0) + 1
                src = data.column("source")[i].as_py()
                sources[src] = sources.get(src, 0) + 1

            print("  By category:", ", ".join(f"{k}={v}" for k, v in sorted(cats.items())))
            print("  By tier:", ", ".join(f"{k}={v}" for k, v in sorted(tiers.items())))
            print("  By source:", ", ".join(f"{k}={v}" for k, v in sorted(sources.items())))
    else:
        print("\n  No memories stored yet.")

    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="openclawd",
        description="OpenClawdCode management CLI",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("doctor", help="Check installation health")
    sub.add_parser("stats", help="Show memory statistics")

    args = parser.parse_args()

    if args.command == "doctor":
        sys.exit(cmd_doctor())
    elif args.command == "stats":
        sys.exit(cmd_stats())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
