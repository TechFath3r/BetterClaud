"""Index an Obsidian vault into LanceDB for semantic search.

Adapted from claudia-optimise/index-obsidian-vault.py — parameterized, no hardcoded paths.
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

from . import config
from .db import VAULT_SCHEMA, get_or_create_table
from .embeddings import embed_batch

STATE_FILE = os.path.expanduser("~/.local/state/betterclaud-vault-index.json")

DEFAULT_EXCLUDES = {
    ".obsidian", ".trash", "Assets", "Archive", "Templates",
}


def load_state(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_state(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f)


def load_custom_excludes(vault_path: str) -> set[str]:
    ignore_file = os.path.join(vault_path, ".vault-index-ignore")
    extra = set()
    if os.path.exists(ignore_file):
        with open(ignore_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    extra.add(line.rstrip("/"))
    return extra


def chunk_by_heading(text: str, filepath: str) -> list[tuple[str, str]]:
    """Split markdown into chunks by h1/h2 headings."""
    chunks = []
    lines = text.split("\n")
    current_heading = os.path.basename(filepath).replace(".md", "")
    current_lines: list[str] = []

    # Strip frontmatter
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                lines = lines[i + 1:]
                break

    for line in lines:
        match = re.match(r"^(#{1,2})\s+(.+)$", line)
        if match:
            if current_lines:
                content = "\n".join(current_lines).strip()
                if len(content) > 50:
                    chunks.append((current_heading, content))
            current_heading = match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        content = "\n".join(current_lines).strip()
        if len(content) > 50:
            chunks.append((current_heading, content))

    # If no headings found, treat whole file as one chunk
    if not chunks and text.strip():
        content = text.strip()
        if len(content) > 50:
            chunks.append((current_heading, content))

    return chunks


def collect_files(
    vault_path: str, excludes: set[str], state: dict, incremental: bool
) -> list[tuple[str, float]]:
    """Walk vault, return list of (filepath, mtime) to index."""
    files = []
    vault = Path(vault_path)
    for md in vault.rglob("*.md"):
        rel = md.relative_to(vault)
        parts = rel.parts
        if any(p.startswith(".") for p in parts):
            continue
        if parts[0] in excludes:
            continue

        mtime = md.stat().st_mtime
        fpath = str(md)

        if incremental:
            prev_mtime = state.get(fpath, 0)
            if mtime <= prev_mtime:
                continue

        files.append((fpath, mtime))
    return files


def index_vault(
    vault_path: str | None = None,
    incremental: bool = False,
    dry_run: bool = False,
) -> str:
    """Index the vault. Returns status message."""
    vault_path = vault_path or config.VAULT_PATH
    if not vault_path:
        return "No vault path configured."

    if not os.path.isdir(vault_path):
        return f"Vault path does not exist: {vault_path}"

    excludes = DEFAULT_EXCLUDES | load_custom_excludes(vault_path)
    state = load_state(STATE_FILE) if incremental else {}

    files = collect_files(vault_path, excludes, state, incremental)
    if not files:
        return "Nothing to index."

    if dry_run:
        lines = [f"  Would index: {f}" for f, _ in files]
        lines.append(f"\n{len(files)} files to index.")
        return "\n".join(lines)

    print(f"Indexing {len(files)} files...", file=sys.stderr)

    # Collect all chunks
    all_chunks: list[dict] = []
    new_state = state.copy() if incremental else {}

    for fpath, mtime in files:
        try:
            text = Path(fpath).read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"  Skip {fpath}: {e}", file=sys.stderr)
            continue

        rel_path = os.path.relpath(fpath, vault_path)
        chunks = chunk_by_heading(text, fpath)

        for heading, content in chunks:
            if len(content) > 2000:
                content = content[:2000]

            chunk_id = hashlib.sha256(f"{rel_path}::{heading}".encode()).hexdigest()[:16]
            all_chunks.append({
                "id": chunk_id,
                "text": content,
                "filepath": rel_path,
                "heading": heading,
                "modified": mtime,
            })

        new_state[fpath] = mtime

    if not all_chunks:
        return "No content to index."

    # Embed in batches
    print(f"Embedding {len(all_chunks)} chunks...", file=sys.stderr)
    texts = [c["text"] for c in all_chunks]
    vectors = embed_batch(texts)
    for chunk, vec in zip(all_chunks, vectors):
        chunk["vector"] = vec

    # Write to LanceDB
    from .db import get_db
    db = get_db()
    table_name = config.VAULT_TABLE

    if incremental and table_name in db.table_names():
        table = db.open_table(table_name)
        re_indexed_paths = {c["filepath"] for c in all_chunks}
        for rp in re_indexed_paths:
            try:
                table.delete(f"filepath = '{rp}'")
            except Exception:
                pass
        table.add(all_chunks)
    else:
        if table_name in db.table_names():
            db.drop_table(table_name)
        db.create_table(table_name, data=all_chunks, schema=VAULT_SCHEMA)

    save_state(STATE_FILE, new_state)
    return f"Indexed {len(all_chunks)} chunks from {len(files)} files."
