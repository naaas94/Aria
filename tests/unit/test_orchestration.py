"""Unit tests for the scratch orchestration engine.

Tests state transitions, edge routing, execution engine, and golden
path traces without requiring external services.
"""

from __future__ import annotations

from typing import Any

import pytest

from aria.orchestration.scratch.edges import (
    route_after_graph_builder,
    route_after_impact_analyzer,
    route_after_ingestion,
    route_after_supervisor,
)
from aria.orchestration.scratch.graph import OrchestrationGraph, build_default_graph
from aria.orchestration.scratch.nodes import ToolPorts
from aria.orchestration.scratch.state import ARIAState


class MockToolPorts:
    """Stub tool ports for testing without external services."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self._should_fail = should_fail
        self.calls: list[str] = []

    async def extract_entities(self, text: str, doc_hash: str) -> dict:
        self.calls.append("extract_entities")
        if self._should_fail:
            raise RuntimeError("Mock extraction failure")
        return {
            "schema_version": "0.1.0",
            "source_document_hash": doc_hash,
            "regulations": [],
            "jurisdictions": [],
            "teams": [],
            "policy_documents": [],
            "internal_systems": [],
        }

    async def write_to_graph(self, entities: dict) -> dict:
        self.calls.append("write_to_graph")
        return {"nodes_created": 1, "nodes_merged": 0, "edges_created": 0, "edges_merged": 0, "errors": []}

    async def index_vectors(self, chunks: list[dict]) -> bool:
        self.calls.append("index_vectors")
        return True

    async def query_graph(self, query_name: str, params: dict) -> list[dict]:
        self.calls.append(f"query_graph:{query_name}")
        return [
            {
                "regulation": "Test Regulation",
                "article": "1",
                "article_id": "art-1",
                "requirement_id": "req-1",
                "requirement": "Test requirement",
                "obligation_type": "requirement",
                "system_id": "sys-1",
                "system_name": "Test System",
                "team": "Test Team",
                "team_id": "team-1",
                "policy_id": None,
                "policy_title": None,
            }
        ]

    async def vector_search(self, query: str, top_k: int) -> list[dict]:
        self.calls.append("vector_search")
        return []

    async def generate_text(self, messages: list[dict]) -> str:
        self.calls.append("generate_text")
        return "Generated report content"


class TestEdgeRouting:
    def test_supervisor_routes_to_ingestion(self):
        state = ARIAState(raw_document="some doc content")
        assert route_after_supervisor(state) == "ingestion"

    def test_supervisor_routes_to_impact(self):
        state = ARIAState(regulation_id="reg-1")
        assert route_after_supervisor(state) == "impact_analyzer"

    def test_supervisor_routes_to_end_on_empty(self):
        state = ARIAState()
        assert route_after_supervisor(state) == "end"

    def test_supervisor_routes_to_end_on_error(self):
        state = ARIAState(error="something broke")
        assert route_after_supervisor(state) == "end"

    def test_ingestion_routes_to_graph_builder(self):
        from aria.contracts.regulation import ExtractedEntities
        state = ARIAState(
            extracted_entities=ExtractedEntities(
                source_document_hash="h", regulations=[]
            )
        )
        assert route_after_ingestion(state) == "graph_builder"

    def test_ingestion_routes_to_end_on_error(self):
        state = ARIAState(error="extraction failed")
        assert route_after_ingestion(state) == "end"

    def test_impact_routes_to_report_generator(self):
        from aria.contracts.impact import ImpactReport
        state = ARIAState(
            impact_report=ImpactReport(
                regulation_id="r1", regulation_title="Test"
            )
        )
        assert route_after_impact_analyzer(state) == "report_generator"

    def test_graph_builder_routes_to_impact_if_regulation_id(self):
        state = ARIAState(regulation_id="reg-1")
        assert route_after_graph_builder(state) == "impact_analyzer"

    def test_graph_builder_routes_to_end_without_regulation_id(self):
        state = ARIAState()
        assert route_after_graph_builder(state) == "end"


class TestARIAState:
    def test_ingestion_request_detection(self):
        state = ARIAState(raw_document="content")
        assert state.is_ingestion_request
        assert not state.is_impact_query

    def test_impact_query_detection(self):
        state = ARIAState(regulation_id="reg-1")
        assert state.is_impact_query
        assert not state.is_ingestion_request

    def test_history_recording(self):
        state = ARIAState()
        state.record_step("supervisor")
        state.record_step("ingestion")
        assert state.history == ["supervisor", "ingestion"]
        assert state.current_node == "ingestion"


class TestOrchestrationExecution:
    @pytest.mark.asyncio
    async def test_ingestion_flow(self):
        graph = build_default_graph()
        tools = MockToolPorts()
        state = ARIAState(raw_document="Test document content", document_hash="abc123")

        result = await graph.execute(state, tools)

        assert result.success
        assert "supervisor" in result.node_path
        assert "ingestion" in result.node_path
        assert "end" in result.node_path

    @pytest.mark.asyncio
    async def test_impact_query_flow(self):
        graph = build_default_graph()
        tools = MockToolPorts()
        state = ARIAState(regulation_id="reg-test")

        result = await graph.execute(state, tools)

        assert result.success
        assert "supervisor" in result.node_path
        assert "impact_analyzer" in result.node_path
        assert "report_generator" in result.node_path

    @pytest.mark.asyncio
    async def test_empty_state_terminates(self):
        graph = build_default_graph()
        tools = MockToolPorts()
        state = ARIAState()

        result = await graph.execute(state, tools)

        assert result.success
        assert result.node_path == ["supervisor", "end"]

    @pytest.mark.asyncio
    async def test_error_propagation(self):
        graph = build_default_graph()
        tools = MockToolPorts(should_fail=True)
        state = ARIAState(raw_document="Test doc")

        result = await graph.execute(state, tools)

        assert not result.success
        assert result.final_state.error is not None

    @pytest.mark.asyncio
    async def test_trace_structure(self):
        graph = build_default_graph()
        tools = MockToolPorts()
        state = ARIAState(regulation_id="reg-1")

        result = await graph.execute(state, tools)
        trace = result.to_trace_dict()

        assert "success" in trace
        assert "total_duration_ms" in trace
        assert "node_path" in trace
        assert len(trace["steps"]) > 0
