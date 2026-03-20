"""Tests for vault search."""

import os
from unittest import mock

import pytest


@pytest.fixture
def temp_db(tmp_path):
    env = os.environ.copy()
    env["BETTERCLAUD_LANCEDB_PATH"] = str(tmp_path / "lancedb")
    env["BETTERCLAUD_VAULT_PATH"] = str(tmp_path / "vault")
    with mock.patch.dict(os.environ, env):
        import importlib
        from betterclaud import config, db
        importlib.reload(config)
        db.get_db.cache_clear()
        importlib.reload(db)
        yield tmp_path


@pytest.fixture
def mock_embed():
    vec = [0.1] * 768
    with mock.patch("betterclaud.tools.vault_search.embed_one", return_value=vec):
        yield vec


def test_empty_vault(temp_db, mock_embed):
    from betterclaud.tools.vault_search import vault_search

    result = vault_search("anything")
    assert "empty" in result.lower() or "index" in result.lower()


def test_vault_search_with_data(temp_db, mock_embed):
    from betterclaud.tools.vault_search import vault_search
    from betterclaud.db import get_or_create_table, VAULT_SCHEMA
    from betterclaud import config

    # Insert some test data
    table = get_or_create_table(config.VAULT_TABLE, VAULT_SCHEMA)
    table.add([{
        "id": "test1",
        "text": "How to set up NFS on Proxmox",
        "vector": mock_embed,
        "filepath": "Homelab/NFS.md",
        "heading": "NFS Setup",
        "modified": 1710000000.0,
    }])

    result = vault_search("NFS setup")
    assert "NFS" in result
    assert "Homelab/NFS.md" in result
