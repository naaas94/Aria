"""Unit tests for the hybrid retrieval pipeline and reranker."""

from __future__ import annotations

from aria.retrieval.reranker import RerankedResult, rerank_results
from aria.retrieval.graph_retriever import GraphContext
from aria.retrieval.vector_store import RetrievedChunk


def _make_chunk(chunk_id: str, score: float, text: str = "test") -> RetrievedChunk:
    return RetrievedChunk(chunk_id=chunk_id, text=text, score=score, metadata={})


class TestReranker:
    def test_vector_only_results(self):
        chunks = [
            _make_chunk("c1", 0.9, "high relevance"),
            _make_chunk("c2", 0.5, "medium relevance"),
            _make_chunk("c3", 0.2, "low relevance"),
        ]
        results = rerank_results(chunks, [])
        assert len(results) == 3
        assert results[0].chunk_id == "c1"
        assert results[0].source == "vector"

    def test_graph_boost_applied(self):
        chunks = [
            _make_chunk("c1", 0.7, "chunk one"),
            _make_chunk("c2", 0.75, "chunk two"),
        ]
        graph_contexts = [
            GraphContext(
                anchor_id="c1",
                anchor_label="Article",
                neighbors=[{"id": "c1"}],
            )
        ]
        results = rerank_results(chunks, graph_contexts)
        boosted = next(r for r in results if r.chunk_id == "c1")
        unboosted = next(r for r in results if r.chunk_id == "c2")
        assert boosted.score > unboosted.score
        assert boosted.source == "both"

    def test_graph_only_results_included(self):
        graph_contexts = [
            GraphContext(
                anchor_id="graph-only-1",
                anchor_label="Requirement",
                neighbors=[{"id": "n1"}],
            )
        ]
        results = rerank_results([], graph_contexts)
        assert len(results) == 1
        assert results[0].source == "graph"

    def test_max_results_limit(self):
        chunks = [_make_chunk(f"c{i}", 0.9 - i * 0.01) for i in range(20)]
        results = rerank_results(chunks, [], max_results=5)
        assert len(results) == 5

    def test_min_score_threshold(self):
        chunks = [
            _make_chunk("high", 0.8),
            _make_chunk("low", 0.05),
        ]
        results = rerank_results(chunks, [])
        ids = [r.chunk_id for r in results]
        assert "high" in ids
        assert "low" not in ids

    def test_results_sorted_by_score(self):
        chunks = [
            _make_chunk("a", 0.3),
            _make_chunk("b", 0.9),
            _make_chunk("c", 0.6),
        ]
        results = rerank_results(chunks, [])
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)
