"""Tests for cross-encoder reranker (LLM-based scoring)."""

from unittest import mock
import pytest


class TestRerankBlending:
    def test_blend_formula(self):
        """Reranker blends: final = 0.6*rerank + 0.4*fused."""
        from openclawd.reranker import rerank

        candidates = [
            {"id": "m1", "content": "foo", "fused_score": 0.5},
            {"id": "m2", "content": "bar", "fused_score": 0.8},
        ]

        def fake_score(query, content):
            return 0.9 if "foo" in content else 0.3

        with mock.patch("openclawd.reranker._score_one", side_effect=fake_score), \
             mock.patch("openclawd.reranker.config") as mock_config:
            mock_config.RERANK_BLEND = 0.6
            result = rerank("test query", candidates)

        # m1: 0.6*0.9 + 0.4*0.5 = 0.54 + 0.20 = 0.74
        # m2: 0.6*0.3 + 0.4*0.8 = 0.18 + 0.32 = 0.50
        assert result[0]["id"] == "m1"  # m1 now ranked higher after rerank
        assert result[0]["fused_score"] == pytest.approx(0.74, rel=1e-3)
        assert result[1]["fused_score"] == pytest.approx(0.50, rel=1e-3)

    def test_failed_scoring_preserves_original(self):
        """If LLM scoring fails, original fused_score is kept."""
        from openclawd.reranker import rerank

        candidates = [{"id": "m1", "content": "foo", "fused_score": 0.7}]

        with mock.patch("openclawd.reranker._score_one", return_value=None), \
             mock.patch("openclawd.reranker.config") as mock_config:
            mock_config.RERANK_BLEND = 0.6
            result = rerank("query", candidates)

        assert result[0]["fused_score"] == 0.7
        assert result[0]["rerank_score"] is None

    def test_score_clamped_to_0_1(self):
        """Scores outside [0,1] are clamped."""
        from openclawd.reranker import _score_one

        # Mock httpx to return "1.5" (out of range)
        class FakeResp:
            def raise_for_status(self): pass
            def json(self): return {"message": {"content": "1.5"}}

        with mock.patch("openclawd.reranker.httpx.post", return_value=FakeResp()), \
             mock.patch("openclawd.reranker.config") as mock_config:
            mock_config.RERANK_MODEL = ""
            mock_config.EXTRACTOR_OLLAMA_MODEL = "test"
            mock_config.OLLAMA_URL = "http://localhost:11434"
            score = _score_one("q", "d")

        assert score == 1.0  # clamped

    def test_reorder_by_reranked_score(self):
        """Results are sorted by final blended score descending."""
        from openclawd.reranker import rerank

        candidates = [
            {"id": "m1", "content": "low", "fused_score": 0.9},
            {"id": "m2", "content": "high", "fused_score": 0.3},
        ]

        # Reranker flips the order
        def fake(q, c):
            return 0.1 if "low" in c else 1.0

        with mock.patch("openclawd.reranker._score_one", side_effect=fake), \
             mock.patch("openclawd.reranker.config") as mock_config:
            mock_config.RERANK_BLEND = 0.6
            result = rerank("query", candidates)

        assert result[0]["id"] == "m2"
