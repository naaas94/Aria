"""Unit tests for ``aria.services.compliance_query`` (mocked retrieval / LLM)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria.retrieval.hybrid_retriever import HybridResult
from aria.retrieval.reranker import RerankedResult
from aria.retrieval.vector_store import RetrievedChunk
from aria.services.compliance_query import (
    ComplianceQueryRequest,
    ComplianceQuerySuccess,
    ComplianceQueryUnavailable,
    run_compliance_query,
)


@pytest.mark.asyncio
async def test_placeholder_returns_trace_and_strategy() -> None:
    req = ComplianceQueryRequest(
        question="Q?",
        regulation_id="reg-1",
        use_graph_rag=True,
        top_k=5,
    )
    conns = MagicMock(neo4j=None, vector_store=None)
    out = await run_compliance_query(req, conns, use_placeholder=True)
    assert isinstance(out, ComplianceQuerySuccess)
    assert out.aria_mode == "placeholder"
    assert out.response.retrieval_strategy == "graphrag"
    assert out.response.trace["top_k"] == 5
    assert out.response.trace["regulation_id"] == "reg-1"
    assert "reg-1" in out.response.answer


@pytest.mark.asyncio
async def test_placeholder_vector_only() -> None:
    req = ComplianceQueryRequest(question="Q?", use_graph_rag=False, top_k=3)
    conns = MagicMock(neo4j=None, vector_store=None)
    out = await run_compliance_query(req, conns, use_placeholder=True)
    assert isinstance(out, ComplianceQuerySuccess)
    assert out.response.retrieval_strategy == "vector_only"


@pytest.mark.asyncio
async def test_live_graphrag_missing_chroma() -> None:
    req = ComplianceQueryRequest(question="Q?", use_graph_rag=True)
    conns = MagicMock(neo4j=MagicMock(), vector_store=None)
    out = await run_compliance_query(req, conns, use_placeholder=False)
    assert isinstance(out, ComplianceQueryUnavailable)
    assert "chroma" in out.missing_dependencies


@pytest.mark.asyncio
async def test_live_graphrag_missing_neo4j() -> None:
    req = ComplianceQueryRequest(question="Q?", use_graph_rag=True)
    conns = MagicMock(neo4j=None, vector_store=MagicMock())
    out = await run_compliance_query(req, conns, use_placeholder=False)
    assert isinstance(out, ComplianceQueryUnavailable)
    assert "neo4j" in out.missing_dependencies


@pytest.mark.asyncio
async def test_live_vector_only_missing_chroma() -> None:
    req = ComplianceQueryRequest(question="Q?", use_graph_rag=False)
    conns = MagicMock(neo4j=None, vector_store=None)
    out = await run_compliance_query(req, conns, use_placeholder=False)
    assert isinstance(out, ComplianceQueryUnavailable)
    assert out.missing_dependencies == ["chroma"]


@pytest.mark.asyncio
async def test_live_vector_only_success() -> None:
    req = ComplianceQueryRequest(question="What applies?", use_graph_rag=False, top_k=2)
    chunk = RetrievedChunk("c1", "excerpt text", 0.9, {})
    vs = MagicMock()
    vs.search = MagicMock(return_value=[chunk])
    conns = MagicMock(neo4j=None, vector_store=vs)

    with patch("aria.services.compliance_query.LLMClient") as llm_cls:
        llm_cls.return_value.complete = AsyncMock(return_value="final answer")
        out = await run_compliance_query(req, conns, use_placeholder=False)

    assert isinstance(out, ComplianceQuerySuccess)
    assert out.aria_mode == "live"
    assert out.response.answer == "final answer"
    assert len(out.response.sources) == 1
    assert out.response.sources[0]["text"] == "excerpt text"
    vs.search.assert_called_once()


@pytest.mark.asyncio
async def test_live_graphrag_success() -> None:
    req = ComplianceQueryRequest(
        question="Scoped?",
        regulation_id="reg-x",
        use_graph_rag=True,
        top_k=3,
    )
    neo = MagicMock()
    vs = MagicMock()
    conns = MagicMock(neo4j=neo, vector_store=vs)

    rr = RerankedResult(chunk_id="c1", text="ctx line", score=0.88, source="vector")
    hybrid_result = HybridResult(
        vector_chunks=[],
        graph_contexts=[],
        reranked=[rr],
    )

    with (
        patch("aria.services.compliance_query.HybridRetriever") as hybrid_retriever_cls,
        patch("aria.services.compliance_query.LLMClient") as llm_cls,
    ):
        hybrid_retriever_cls.return_value.retrieve = AsyncMock(return_value=hybrid_result)
        llm_cls.return_value.complete = AsyncMock(return_value="graphrag answer")
        out = await run_compliance_query(req, conns, use_placeholder=False)

    assert isinstance(out, ComplianceQuerySuccess)
    assert out.aria_mode == "live"
    assert out.response.answer == "graphrag answer"
    assert out.response.sources[0]["text"] == "ctx line"
    hybrid_retriever_cls.return_value.retrieve.assert_awaited_once()
