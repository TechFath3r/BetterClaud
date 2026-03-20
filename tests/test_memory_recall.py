"""Tests for memory recall filtering."""

import os
from unittest import mock

import pytest


@pytest.fixture
def temp_db(tmp_path):
    env = os.environ.copy()
    env["BETTERCLAUD_LANCEDB_PATH"] = str(tmp_path / "lancedb")
    with mock.patch.dict(os.environ, env):
        import importlib
        from betterclaud import config, db
        importlib.reload(config)
        db.get_db.cache_clear()
        importlib.reload(db)
        yield


@pytest.fixture
def mock_embed():
    vec = [0.1] * 768
    with mock.patch("betterclaud.tools.memory_store.embed_one", return_value=vec), \
         mock.patch("betterclaud.tools.memory_recall.embed_one", return_value=vec):
        yield


def test_empty_db(temp_db, mock_embed):
    from betterclaud.tools.memory_recall import memory_recall

    result = memory_recall("anything")
    assert "No memories stored" in result


def test_category_filter(temp_db, mock_embed):
    from betterclaud.tools.memory_store import memory_store
    from betterclaud.tools.memory_recall import memory_recall

    memory_store("I like dark mode", category="preference")
    memory_store("Fixed the auth bug", category="debugging")

    result = memory_recall("user preferences", category="preference")
    assert "dark mode" in result


def test_importance_filter(temp_db, mock_embed):
    from betterclaud.tools.memory_store import memory_store
    from betterclaud.tools.memory_recall import memory_recall

    memory_store("trivial thing", importance=1)
    memory_store("critical thing", importance=10)

    result = memory_recall("things", min_importance=8)
    assert "critical thing" in result
