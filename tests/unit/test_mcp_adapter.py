"""Unit tests for MCP adapter wiring and orchestrated query entry."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from api.connections import AppConnections
from aria.protocols.mcp.server import MCPServer, MCPToolPortsAdapter
from aria.services.compliance_query import ComplianceQueryRequest, ComplianceQueryUnavailable
from aria.services.orchestrated_query import build_mcp_adapter, run_orchestrated_query


def test_mcp_adapter_construction() -> None:
    server = MCPServer(neo4j_client=None, vector_store=None)
    adapter = MCPToolPortsAdapter(mcp_server=server)
    assert adapter is not None


def test_run_orchestrated_query_missing_deps_returns_unavailable() -> None:
    req = ComplianceQueryRequest(question="What applies?")
    result = asyncio.run(run_orchestrated_query(req, AppConnections()))
    assert isinstance(result, ComplianceQueryUnavailable)
    assert "neo4j" in result.missing_dependencies
    assert "chroma" in result.missing_dependencies


@pytest.mark.asyncio
async def test_index_vectors_delegates_to_vector_store_index_chunks() -> None:
    vs = MagicMock()
    vs.index_chunks = MagicMock(return_value=1)
    server = MCPServer(neo4j_client=None, vector_store=vs)
    adapter = MCPToolPortsAdapter(mcp_server=server)
    ok = await adapter.index_vectors(
        [
            {
                "chunk_id": "c1",
                "text": "body",
                "metadata": {"source_hash": "abc123"},
            }
        ]
    )
    assert ok is True
    vs.index_chunks.assert_called_once()
    indexed = vs.index_chunks.call_args[0][0]
    assert len(indexed) == 1
    assert indexed[0].chunk_id == "c1"
    assert indexed[0].source_document_hash == "abc123"
