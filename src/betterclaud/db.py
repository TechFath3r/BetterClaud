"""LanceDB connection and table schemas."""

import os
from functools import lru_cache

import lancedb
import pyarrow as pa

from . import config

# --- Schemas ---

MEMORY_SCHEMA = pa.schema([
    pa.field("id", pa.string()),
    pa.field("content", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), config.EMBED_DIM)),
    pa.field("category", pa.string()),
    pa.field("project", pa.string()),
    pa.field("tags", pa.string()),          # JSON-encoded list
    pa.field("importance", pa.int32()),
    pa.field("created_at", pa.float64()),
    pa.field("updated_at", pa.float64()),
    pa.field("source", pa.string()),
])

VAULT_SCHEMA = pa.schema([
    pa.field("id", pa.string()),
    pa.field("text", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), config.EMBED_DIM)),
    pa.field("filepath", pa.string()),
    pa.field("heading", pa.string()),
    pa.field("modified", pa.float64()),
])


# --- Connection ---

@lru_cache(maxsize=1)
def get_db() -> lancedb.DBConnection:
    """Get or create the LanceDB connection."""
    os.makedirs(config.LANCEDB_PATH, exist_ok=True)
    return lancedb.connect(config.LANCEDB_PATH)


def get_or_create_table(name: str, schema: pa.Schema) -> lancedb.table.Table:
    """Open a table, creating it if it doesn't exist."""
    db = get_db()
    if name in db.table_names():
        return db.open_table(name)
    return db.create_table(name, schema=schema)
