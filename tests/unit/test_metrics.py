"""Unit tests for Prometheus metrics instrumentation.

Verifies that each instrumented code path increments its counter and
records histogram observations. Uses delta checks so tests remain
independent regardless of execution order or global counter state.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from prometheus_client import REGISTRY

from aria.observability.metrics import (
    AGENT_EXECUTION_COUNTER,
    AGENT_EXECUTION_DURATION,
    GRAPH_QUERY_COUNTER,
    INGESTION_COUNTER,
    INGESTION_DURATION,
    LLM_CALL_COUNTER,
    LLM_CALL_DURATION,
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
        before = _counter_value(LLM_CALL_COUNTER, model="ollama/llama3.2", status="success")
        before_hist = _histogram_count("aria_llm_call_duration_seconds", {"model": "ollama/llama3.2"})

        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(message=AsyncMock(content="Hello world"))]

        with patch("litellm.acompletion", return_value=mock_response):
            from aria.llm.client import LLMClient

            client = LLMClient()
            result = await client.complete([{"role": "user", "content": "Hi"}])

        assert result == "Hello world"
        assert _counter_value(LLM_CALL_COUNTER, model="ollama/llama3.2", status="success") == before + 1
        assert _histogram_count("aria_llm_call_duration_seconds", {"model": "ollama/llama3.2"}) == before_hist + 1

    @pytest.mark.asyncio
    async def test_complete_failure(self):
        before = _counter_value(LLM_CALL_COUNTER, model="ollama/llama3.2", status="error")

        with patch("litellm.acompletion", side_effect=RuntimeError("LLM down")):
            from aria.llm.client import LLMClient

            client = LLMClient(max_retries=1)
            with pytest.raises(RuntimeError, match="LLM down"):
                await client.complete([{"role": "user", "content": "Hi"}])

        assert _counter_value(LLM_CALL_COUNTER, model="ollama/llama3.2", status="error") == before + 1


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
def client():
    from starlette.testclient import TestClient

    from api.main import app

    with TestClient(app) as c:
        yield c
