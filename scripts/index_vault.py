#!/usr/bin/env python3
"""CLI wrapper for vault indexer.

Usage:
    betterclaud-index [--incremental] [--vault /path] [--dry-run]
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Index Obsidian vault into LanceDB")
    parser.add_argument("--incremental", action="store_true", help="Only re-index changed files")
    parser.add_argument("--vault", default=None, help="Override vault path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be indexed")
    args = parser.parse_args()

    from betterclaud.vault_indexer import index_vault

    result = index_vault(
        vault_path=args.vault,
        incremental=args.incremental,
        dry_run=args.dry_run,
    )
    print(result)


if __name__ == "__main__":
    main()
