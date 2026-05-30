"""Unit tests for Neo4jClient observability instrumentation."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from prometheus_client import REGISTRY

from aria.observability.metrics import GRAPH_QUERY_COUNTER


def _counter_value(counter, **labels) -> float:
    return counter.labels(**labels)._value.get()


def _histogram_count(name: str, labels: dict[str, str]) -> float:
    val = REGISTRY.get_sample_value(f"{name}_count", labels)
    return val if val is not None else 0.0


class _EmptyAsyncResult:
    """Minimal async iterable for mocking session.run() on Python 3.14+."""

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class TestNeo4jClientGraphQueryDuration:
    @pytest.mark.asyncio
    async def test_execute_read_observes_duration_histogram(self):
        from aria.graph.client import Neo4jClient

        client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
        before_hist = _histogram_count(
            "aria_graph_query_duration_seconds", {"query_name": "read"}
        )

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=_EmptyAsyncResult())

        with patch.object(client, "session") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            await client.execute_read("RETURN 1")

        assert (
            _histogram_count("aria_graph_query_duration_seconds", {"query_name": "read"})
            == before_hist + 1
        )

    @pytest.mark.asyncio
    async def test_execute_write_observes_duration_histogram(self):
        from aria.graph.client import Neo4jClient

        client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
        before_hist = _histogram_count(
            "aria_graph_query_duration_seconds", {"query_name": "write"}
        )

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=_EmptyAsyncResult())

        with patch.object(client, "session") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            await client.execute_write("CREATE (n:Test)")

        assert (
            _histogram_count("aria_graph_query_duration_seconds", {"query_name": "write"})
            == before_hist + 1
        )

    @pytest.mark.asyncio
    async def test_execute_read_error_does_not_observe_histogram(self):
        """Query failure must not record duration (exception propagates)."""
        from aria.graph.client import Neo4jClient

        client = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
        before = _counter_value(GRAPH_QUERY_COUNTER, query_name="read")
        before_hist = _histogram_count(
            "aria_graph_query_duration_seconds", {"query_name": "read"}
        )

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(side_effect=RuntimeError("read failed"))

        with patch.object(client, "session") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(RuntimeError, match="read failed"):
                await client.execute_read("RETURN 1")

        assert _counter_value(GRAPH_QUERY_COUNTER, query_name="read") == before + 1
        assert (
            _histogram_count("aria_graph_query_duration_seconds", {"query_name": "read"})
            == before_hist
        )
