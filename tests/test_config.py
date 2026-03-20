"""Tests for config module."""

import os
from unittest import mock


def test_defaults():
    """Config provides sensible defaults without any env vars."""
    # Clear any betterclaud env vars
    env = {k: v for k, v in os.environ.items() if not k.startswith("BETTERCLAUD_")}
    with mock.patch.dict(os.environ, env, clear=True):
        # Re-import to pick up env changes
        import importlib
        from betterclaud import config

        importlib.reload(config)

        assert "betterclaud/lancedb" in config.LANCEDB_PATH
        assert config.OLLAMA_URL == "http://localhost:11434"
        assert config.EMBED_MODEL == "nomic-embed-text"
        assert config.EMBED_DIM == 768
        assert config.VAULT_PATH == ""
        assert config.CHROMADB_PATH == ""


def test_env_override():
    """Config reads from environment variables."""
    env = os.environ.copy()
    env["BETTERCLAUD_EMBED_MODEL"] = "test-model"
    env["BETTERCLAUD_EMBED_DIM"] = "384"

    with mock.patch.dict(os.environ, env, clear=True):
        import importlib
        from betterclaud import config

        importlib.reload(config)

        assert config.EMBED_MODEL == "test-model"
        assert config.EMBED_DIM == 384
