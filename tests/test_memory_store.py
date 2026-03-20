"""Tests for memory store and recall."""

import os
import tempfile
from unittest import mock

import pytest


@pytest.fixture
def temp_db(tmp_path):
    """Set up a temp LanceDB directory and mock Ollama."""
    env = os.environ.copy()
    env["BETTERCLAUD_LANCEDB_PATH"] = str(tmp_path / "lancedb")

    with mock.patch.dict(os.environ, env):
        import importlib
        from betterclaud import config, db

        importlib.reload(config)
        # Clear the lru_cache so db picks up new path
        db.get_db.cache_clear()
        importlib.reload(db)

        yield tmp_path


@pytest.fixture
def mock_embed():
    """Mock the embedding function to return a fixed vector."""
    vec = [0.1] * 768

    with mock.patch("betterclaud.tools.memory_store.embed_one", return_value=vec), \
         mock.patch("betterclaud.tools.memory_recall.embed_one", return_value=vec):
        yield vec


def test_store_and_recall(temp_db, mock_embed):
    from betterclaud.tools.memory_store import memory_store
    from betterclaud.tools.memory_recall import memory_recall

    result = memory_store("Python prefers spaces over tabs", category="preference")
    assert "Memory stored" in result

    result = memory_recall("coding style preferences")
    assert "spaces over tabs" in result


def test_dedup(temp_db, mock_embed):
    from betterclaud.tools.memory_store import memory_store
    from betterclaud.db import get_or_create_table, MEMORY_SCHEMA
    from betterclaud import config

    memory_store("duplicate test content")
    memory_store("duplicate test content")

    table = get_or_create_table(config.MEMORY_TABLE, MEMORY_SCHEMA)
    # Should only have one row since content hash is the same
    assert table.count_rows() == 1


def test_invalid_category(temp_db, mock_embed):
    from betterclaud.tools.memory_store import memory_store

    result = memory_store("test", category="invalid_cat")
    assert "Invalid category" in result


def test_importance_clamping(temp_db, mock_embed):
    from betterclaud.tools.memory_store import memory_store

    # Should not raise even with out-of-range importance
    result = memory_store("test", importance=99)
    assert "Memory stored" in result
    result = memory_store("test2", importance=-5)
    assert "Memory stored" in result
