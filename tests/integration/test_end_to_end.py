"""End-to-end integration tests.

Tests critical workflows across multiple layers without requiring
external services (Neo4j, ChromaDB, Ollama).
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import app
from aria.contracts.regulation import (
    Article,
    ExtractedEntities,
    ObligationType,
    Regulation,
    Requirement,
)
from aria.graph.builder import entities_to_write_payload
from aria.orchestration.scratch.graph import build_default_graph
from aria.orchestration.scratch.state import ARIAState


client = TestClient(app)


class TestAPIEndpoints:
    def test_health(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_ingest_text(self):
        response = client.post("/ingest/text", json={
            "text": "Article 1. This regulation applies to all AI systems.",
            "source": "test",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["document_hash"]
        assert data["chunks_produced"] >= 0

    def test_ingest_empty_text_rejected(self):
        response = client.post("/ingest/text", json={"text": "  "})
        assert response.status_code == 400

    def test_query_endpoint(self):
        response = client.post("/query", json={
            "question": "What requirements affect our ML systems?",
        })
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data

    def test_impact_endpoint(self):
        response = client.get("/impact/reg-gdpr")
        assert response.status_code == 200
        data = response.json()
        assert data["regulation_id"] == "reg-gdpr"

    def test_agents_list(self):
        response = client.get("/agents")
        assert response.status_code == 200
        agents = response.json()
        assert len(agents) > 0
        assert all("agent_id" in a for a in agents)

    def test_agent_by_name(self):
        response = client.get("/agents/supervisor")
        assert response.status_code == 200
        assert response.json()["name"] == "Supervisor"

    def test_agent_not_found(self):
        response = client.get("/agents/nonexistent")
        assert response.status_code == 404


class TestContractToGraphFlow:
    """Tests the full contract -> graph payload pipeline without Neo4j."""

    def test_entities_to_payload_conversion(self):
        entities = ExtractedEntities(
            source_document_hash="test-hash",
            regulations=[
                Regulation(
                    id="reg-test",
                    title="Test Regulation",
                    jurisdiction="eu",
                    domain="test",
                    articles=[
                        Article(
                            id="art-1",
                            number="1",
                            title="Scope",
                            text_summary="Test scope",
                            regulation_id="reg-test",
                            requirements=[
                                Requirement(
                                    id="req-1",
                                    text="Must comply with test",
                                    obligation_type=ObligationType.REQUIREMENT,
                                )
                            ],
                        )
                    ],
                )
            ],
        )

        payload = entities_to_write_payload(entities)

        assert len(payload.nodes) >= 3  # regulation + article + requirement
        assert len(payload.edges) >= 2  # CONTAINS + IMPOSES

        labels = [n.label.value for n in payload.nodes]
        assert "Regulation" in labels
        assert "Article" in labels
        assert "Requirement" in labels


class TestOrchestrationFlow:
    """Tests orchestration graph routing without external services."""

    @pytest.mark.asyncio
    async def test_empty_state_routes_to_end(self):
        from tests.unit.test_orchestration import MockToolPorts

        graph = build_default_graph()
        tools = MockToolPorts()
        state = ARIAState()

        result = await graph.execute(state, tools)
        assert result.success
        assert "end" in result.node_path

    @pytest.mark.asyncio
    async def test_impact_query_produces_report(self):
        from tests.unit.test_orchestration import MockToolPorts

        graph = build_default_graph()
        tools = MockToolPorts()
        state = ARIAState(regulation_id="reg-test")

        result = await graph.execute(state, tools)
        assert result.success
        assert result.final_state.impact_report is not None
        assert result.final_state.final_report is not None
