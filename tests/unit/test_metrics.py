"""Unit tests for Prometheus metrics instrumentation.

Verifies that each instrumented code path increments its counter and
records histogram observations. Uses delta checks so tests remain
independent regardless of execution order or global counter state.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prometheus_client import REGISTRY

from aria.observability.metrics import (
    AGENT_EXECUTION_COUNTER,
    AGENT_EXECUTION_DURATION,
    GRAPH_QUERY_COUNTER,
    GRAPH_QUERY_DURATION,
    HTTP_REQUEST_DURATION,
    INGESTION_COUNTER,
    INGESTION_DURATION,
    LLM_CALL_COUNTER,
    LLM_CALL_DURATION,
    LLM_COST_COUNTER,
    MCP_TOOL_CALL_COUNTER,
    MCP_TOOL_CALL_DURATION,
    RETRIEVAL_COUNTER,
    RETRIEVAL_DURATION,
)


def _counter_value(counter, **labels) -> float:
    return counter.labels(**labels)._value.get()


def _histogram_count(name: str, labels: dict[str, str]) -> float:
    """Get the _count sample from a histogram via the global registry."""
    val = REGISTRY.get_sample_value(f"{name}_count", labels)
    return val if val is not None else 0.0


# ── Ingestion metrics ──────────────────────────────────────────────


class TestIngestionMetrics:
    def test_ingest_text_success(self, client):
        before = _counter_value(INGESTION_COUNTER, status="success")
        before_hist = _histogram_count("aria_ingestion_duration_seconds", {"format": "text"})

        resp = client.post("/ingest/text", json={"text": "Test document content."})
        assert resp.status_code == 200

        assert _counter_value(INGESTION_COUNTER, status="success") == before + 1
        assert _histogram_count("aria_ingestion_duration_seconds", {"format": "text"}) == before_hist + 1

    def test_ingest_file_success(self, client):
        before = _counter_value(INGESTION_COUNTER, status="success")
        before_hist = _histogram_count("aria_ingestion_duration_seconds", {"format": "file"})

        resp = client.post(
            "/ingest/file",
            files={"file": ("test.txt", b"Some regulatory text", "text/plain")},
        )
        assert resp.status_code == 200

        assert _counter_value(INGESTION_COUNTER, status="success") == before + 1
        assert _histogram_count("aria_ingestion_duration_seconds", {"format": "file"}) == before_hist + 1

    def test_ingest_text_empty_body_no_counter(self, client):
        """Validation failure (empty body) happens before the pipeline — counter should not move."""
        before_success = _counter_value(INGESTION_COUNTER, status="success")
        before_error = _counter_value(INGESTION_COUNTER, status="error")

        resp = client.post("/ingest/text", json={"text": "   "})
        assert resp.status_code == 400

        assert _counter_value(INGESTION_COUNTER, status="success") == before_success
        assert _counter_value(INGESTION_COUNTER, status="error") == before_error


# ── Phase 3 metric definitions (T1) ───────────────────────────────


class TestPhase3MetricDefinitions:
    """Contract checks for HTTP_REQUEST_DURATION, GRAPH_QUERY_DURATION, LLM_COST_COUNTER."""

    def test_http_request_duration_contract(self):
        assert HTTP_REQUEST_DURATION._name == "aria_http_request_duration_seconds"
        assert HTTP_REQUEST_DURATION._labelnames == ("method", "status_code")
        assert list(HTTP_REQUEST_DURATION._upper_bounds) == [
            0.005,
            0.01,
            0.025,
            0.05,
            0.1,
            0.25,
            0.5,
            1.0,
            2.5,
            5.0,
            float("inf"),
        ]

    def test_graph_query_duration_contract(self):
        assert GRAPH_QUERY_DURATION._name == "aria_graph_query_duration_seconds"
        assert GRAPH_QUERY_DURATION._labelnames == ("query_name",)
        assert list(GRAPH_QUERY_DURATION._upper_bounds) == [
            0.001,
            0.005,
            0.01,
            0.025,
            0.05,
            0.1,
            0.25,
            0.5,
            1.0,
            float("inf"),
        ]

    def test_llm_cost_counter_contract(self):
        assert LLM_COST_COUNTER._name == "aria_llm_cost_usd"
        assert LLM_COST_COUNTER._labelnames == ("model",)

    def test_phase3_metrics_registered_in_registry(self):
        names = set(REGISTRY._names_to_collectors)
        assert "aria_http_request_duration_seconds" in names
        assert "aria_graph_query_duration_seconds" in names
        assert "aria_llm_cost_usd_total" in names


# ── Agent execution metrics ────────────────────────────────────────


class TestAgentExecutionMetrics:
    @pytest.mark.asyncio
    async def test_agent_run_success(self):
        from aria.agents.base import BaseAgent

        class StubAgent(BaseAgent):
            name = "stub_agent"

            async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
                return {"result": "ok"}

        before = _counter_value(AGENT_EXECUTION_COUNTER, agent_name="stub_agent", status="success")
        before_hist = _histogram_count("aria_agent_execution_duration_seconds", {"agent_name": "stub_agent"})

        agent = StubAgent()
        result = await agent.run({})

        assert result.success
        assert _counter_value(AGENT_EXECUTION_COUNTER, agent_name="stub_agent", status="success") == before + 1
        assert _histogram_count("aria_agent_execution_duration_seconds", {"agent_name": "stub_agent"}) == before_hist + 1

    @pytest.mark.asyncio
    async def test_agent_run_failure(self):
        from aria.agents.base import BaseAgent

        class FailAgent(BaseAgent):
            name = "fail_agent"

            async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
                raise RuntimeError("boom")

        before = _counter_value(AGENT_EXECUTION_COUNTER, agent_name="fail_agent", status="error")

        agent = FailAgent()
        result = await agent.run({})

        assert not result.success
        assert _counter_value(AGENT_EXECUTION_COUNTER, agent_name="fail_agent", status="error") == before + 1


# ── MCP tool call metrics ─────────────────────────────────────────


class TestMCPToolCallMetrics:
    @pytest.mark.asyncio
    async def test_unknown_tool_increments_error(self):
        from aria.protocols.mcp.server import MCPServer

        server = MCPServer()
        before = _counter_value(MCP_TOOL_CALL_COUNTER, tool_name="nonexistent", status="error")

        result = await server.call_tool("nonexistent", {})

        assert not result.success
        assert _counter_value(MCP_TOOL_CALL_COUNTER, tool_name="nonexistent", status="error") == before + 1

    @pytest.mark.asyncio
    async def test_successful_tool_increments_success(self):
        from aria.protocols.mcp.server import MCPServer

        server = MCPServer()
        server._handlers["echo"] = AsyncMock(return_value={"echoed": True})

        before = _counter_value(MCP_TOOL_CALL_COUNTER, tool_name="echo", status="success")
        before_hist = _histogram_count("aria_mcp_tool_call_duration_seconds", {"tool_name": "echo"})

        result = await server.call_tool("echo", {})

        assert result.success
        assert _counter_value(MCP_TOOL_CALL_COUNTER, tool_name="echo", status="success") == before + 1
        assert _histogram_count("aria_mcp_tool_call_duration_seconds", {"tool_name": "echo"}) == before_hist + 1

    @pytest.mark.asyncio
    async def test_failing_tool_increments_error(self):
        from aria.protocols.mcp.server import MCPServer

        server = MCPServer()
        server._handlers["broken"] = AsyncMock(side_effect=RuntimeError("kaboom"))

        before = _counter_value(MCP_TOOL_CALL_COUNTER, tool_name="broken", status="error")
        before_hist = _histogram_count("aria_mcp_tool_call_duration_seconds", {"tool_name": "broken"})

        result = await server.call_tool("broken", {})

        assert not result.success
        assert _counter_value(MCP_TOOL_CALL_COUNTER, tool_name="broken", status="error") == before + 1
        assert _histogram_count("aria_mcp_tool_call_duration_seconds", {"tool_name": "broken"}) == before_hist + 1


# ── Phase 3 instrumentation (T8) ─────────────────────────────────


class TestHTTPDurationHistogram:
    def test_post_request_records_histogram_observation(self, client):
        before = _histogram_count(
            "aria_http_request_duration_seconds",
            {"method": "POST", "status_code": "200"},
        )

        resp = client.post("/ingest/text", json={"text": "Some regulatory content."})
        assert resp.status_code == 200

        after = _histogram_count(
            "aria_http_request_duration_seconds",
            {"method": "POST", "status_code": "200"},
        )
        assert after == before + 1

    def test_skip_paths_do_not_record_histogram(self, client):
        before = _histogram_count(
            "aria_http_request_duration_seconds",
            {"method": "GET", "status_code": "200"},
        )

        client.get("/health")

        after = _histogram_count(
            "aria_http_request_duration_seconds",
            {"method": "GET", "status_code": "200"},
        )
        assert after == before


class TestGraphQueryDurationHistogram:
    @pytest.mark.asyncio
    async def test_execute_read_records_duration(self):
        from aria.graph.client import Neo4jClient

        neo_client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
        before = _histogram_count(
            "aria_graph_query_duration_seconds", {"query_name": "read"}
        )

        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__ = lambda self: aiter([])
        mock_session.run = AsyncMock(return_value=mock_result)

        with patch.object(neo_client, "session") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            await neo_client.execute_read("RETURN 1")

        after = _histogram_count(
            "aria_graph_query_duration_seconds", {"query_name": "read"}
        )
        assert after == before + 1

    @pytest.mark.asyncio
    async def test_execute_write_records_duration(self):
        from aria.graph.client import Neo4jClient

        neo_client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
        before = _histogram_count(
            "aria_graph_query_duration_seconds", {"query_name": "write"}
        )

        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__ = lambda self: aiter([])
        mock_session.run = AsyncMock(return_value=mock_result)

        with patch.object(neo_client, "session") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            await neo_client.execute_write("CREATE (n:Test)")

        after = _histogram_count(
            "aria_graph_query_duration_seconds", {"query_name": "write"}
        )
        assert after == before + 1


class TestLLMCostCounter:
    @pytest.mark.asyncio
    async def test_cost_incremented_when_response_cost_present(self):
        from aria.llm.client import LLMClient

        llm = LLMClient()
        before = _counter_value(LLM_COST_COUNTER, model=llm.model)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="answer"))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response._hidden_params = {"response_cost": 0.005}

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            await llm.complete([{"role": "user", "content": "hello"}])

        after = _counter_value(LLM_COST_COUNTER, model=llm.model)
        assert after == pytest.approx(before + 0.005)

    @pytest.mark.asyncio
    async def test_cost_not_incremented_when_response_cost_none(self):
        from aria.llm.client import LLMClient

        llm = LLMClient()
        before = _counter_value(LLM_COST_COUNTER, model=llm.model)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="answer"))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response._hidden_params = {"response_cost": None}

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
            await llm.complete([{"role": "user", "content": "hello"}])

        after = _counter_value(LLM_COST_COUNTER, model=llm.model)
        assert after == before


class TestIngestionPipelineDuration:
    @pytest.mark.asyncio
    async def test_full_pipeline_records_duration_pdf(self, tmp_path):
        from aria.ingestion.pipeline import ingest_document, reset_ingestion_state

        reset_ingestion_state()

        dummy_pdf = tmp_path / "test.pdf"
        dummy_pdf.write_bytes(b"%PDF-1.4 test")

        before = _histogram_count("aria_ingestion_duration_seconds", {"format": "pdf"})

        with (
            patch(
                "aria.ingestion.pipeline._parse_document",
                return_value=("Some text content", "abc123hash"),
            ),
            patch(
                "aria.ingestion.pipeline.chunk_text",
                return_value=[],
            ),
        ):
            await ingest_document(str(dummy_pdf))

        after = _histogram_count("aria_ingestion_duration_seconds", {"format": "pdf"})
        assert after == before + 1

    @pytest.mark.asyncio
    async def test_skipped_duplicate_does_not_record_duration(self, tmp_path):
        from aria.ingestion.pipeline import (
            IngestionStatus,
            _ingested_hashes,
            ingest_document,
            reset_ingestion_state,
        )

        reset_ingestion_state()
        dummy_pdf = tmp_path / "dup.pdf"
        dummy_pdf.write_bytes(b"%PDF-1.4 dup")

        before = _histogram_count("aria_ingestion_duration_seconds", {"format": "pdf"})

        with patch(
            "aria.ingestion.pipeline._parse_document",
            return_value=("dup text", "dup_hash_999"),
        ):
            _ingested_hashes.add("dup_hash_999")
            result = await ingest_document(str(dummy_pdf))

        assert result.status == IngestionStatus.SKIPPED_DUPLICATE

        after = _histogram_count("aria_ingestion_duration_seconds", {"format": "pdf"})
        assert after == before


# ── Graph query metrics ───────────────────────────────────────────


class TestGraphQueryMetrics:
    @pytest.mark.asyncio
    async def test_execute_read_increments_counter(self):
        from aria.graph.client import Neo4jClient

        client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
        before = _counter_value(GRAPH_QUERY_COUNTER, query_name="read")

        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__ = lambda self: aiter([])
        mock_session.run = AsyncMock(return_value=mock_result)

        with patch.object(client, "session") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            await client.execute_read("RETURN 1")

        assert _counter_value(GRAPH_QUERY_COUNTER, query_name="read") == before + 1

    @pytest.mark.asyncio
    async def test_execute_write_increments_counter(self):
        from aria.graph.client import Neo4jClient

        client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
        before = _counter_value(GRAPH_QUERY_COUNTER, query_name="write")

        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.__aiter__ = lambda self: aiter([])
        mock_session.run = AsyncMock(return_value=mock_result)

        with patch.object(client, "session") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            await client.execute_write("CREATE (n:Test)")

        assert _counter_value(GRAPH_QUERY_COUNTER, query_name="write") == before + 1


# ── LLM call metrics ──────────────────────────────────────────────


class TestLLMCallMetrics:
    @pytest.mark.asyncio
    async def test_complete_success(self):
        from aria.llm.client import LLMClient

        llm = LLMClient()
        before = _counter_value(LLM_CALL_COUNTER, model=llm.model, status="success")
        before_hist = _histogram_count("aria_llm_call_duration_seconds", {"model": llm.model})

        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(message=AsyncMock(content="Hello world"))]

        with patch("litellm.acompletion", return_value=mock_response):
            result = await llm.complete([{"role": "user", "content": "Hi"}])

        assert result == "Hello world"
        assert _counter_value(LLM_CALL_COUNTER, model=llm.model, status="success") == before + 1
        assert _histogram_count("aria_llm_call_duration_seconds", {"model": llm.model}) == before_hist + 1

    @pytest.mark.asyncio
    async def test_complete_failure(self):
        from aria.llm.client import LLMClient

        llm = LLMClient(max_retries=1)
        before = _counter_value(LLM_CALL_COUNTER, model=llm.model, status="error")

        with patch("litellm.acompletion", side_effect=RuntimeError("LLM down")):
            with pytest.raises(RuntimeError, match="LLM down"):
                await llm.complete([{"role": "user", "content": "Hi"}])

        assert _counter_value(LLM_CALL_COUNTER, model=llm.model, status="error") == before + 1


# ── Retrieval metrics (placeholder path) ──────────────────────────


class TestRetrievalMetrics:
    def test_placeholder_query_does_not_increment(self, client):
        """In placeholder mode the retrieval pipeline doesn't run, so counters stay flat."""
        before_graphrag = _counter_value(RETRIEVAL_COUNTER, strategy="graphrag")
        before_vector = _counter_value(RETRIEVAL_COUNTER, strategy="vector_only")

        resp = client.post("/query", json={"question": "What is GDPR?"})
        assert resp.status_code == 200

        assert _counter_value(RETRIEVAL_COUNTER, strategy="graphrag") == before_graphrag
        assert _counter_value(RETRIEVAL_COUNTER, strategy="vector_only") == before_vector


# ── helpers ────────────────────────────────────────────────────────


async def aiter(items):
    for item in items:
        yield item


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ARIA_PLACEHOLDER_API", "true")
    from starlette.testclient import TestClient

    from api.main import app

    with TestClient(app) as c:
        yield c
