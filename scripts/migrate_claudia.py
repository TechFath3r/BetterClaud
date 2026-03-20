#!/usr/bin/env python3
"""One-time migration: Claudia's LanceDB memories → BetterClaud format.

Usage:
    python3 scripts/migrate_claudia.py --source /path/to/claudia/lancedb --table conversations
"""

import argparse
import json
import sys
import time

import lancedb
import pyarrow as pa


def main():
    parser = argparse.ArgumentParser(description="Migrate Claudia memories to BetterClaud")
    parser.add_argument("--source", required=True, help="Path to Claudia's LanceDB directory")
    parser.add_argument("--table", default="conversations", help="Source table name")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    # Import after arg parse so --help works without deps
    from betterclaud import config
    from betterclaud.db import MEMORY_SCHEMA, get_or_create_table

    source_db = lancedb.connect(args.source)

    if args.table not in source_db.table_names():
        print(f"Table '{args.table}' not found in {args.source}")
        print(f"Available tables: {source_db.table_names()}")
        sys.exit(1)

    source_table = source_db.open_table(args.table)
    data = source_table.to_arrow()

    print(f"Found {len(data)} rows in source table.")
    print(f"Columns: {data.column_names}")

    if args.dry_run:
        for i in range(min(3, len(data))):
            for col in data.column_names:
                val = data.column(col)[i].as_py()
                if isinstance(val, list) and len(val) > 5:
                    val = f"[vector: {len(val)} dims]"
                print(f"  {col}: {val}")
            print()
        return

    # Map to new schema
    now = time.time()
    dest_table = get_or_create_table(config.MEMORY_TABLE, MEMORY_SCHEMA)

    migrated = 0
    for i in range(len(data)):
        row = {col: data.column(col)[i].as_py() for col in data.column_names}

        # Adapt fields — adjust these mappings based on actual Claudia schema
        content = row.get("content") or row.get("text") or row.get("message", "")
        vector = row.get("vector", [])

        if not content or not vector:
            continue

        new_row = {
            "id": row.get("id", f"migrated_{i}"),
            "content": content,
            "vector": vector,
            "category": "general",
            "project": "",
            "tags": json.dumps(["migrated-from-claudia"]),
            "importance": 5,
            "created_at": row.get("created_at", row.get("timestamp", now)),
            "updated_at": now,
            "source": "migration",
        }
        dest_table.add([new_row])
        migrated += 1

    print(f"Migrated {migrated} memories to BetterClaud.")


if __name__ == "__main__":
    main()
