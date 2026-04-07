"""API surface, cross-layer contracts, MCP tools, and schema version behavior."""

from __future__ import annotations

import inspect
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from api.main import app
from api.routers import impact as impact_router
from api.routers import ingest as ingest_router
from api.routers import query as query_router
from api.routers.agents import router as agents_router
from api.routers.impact import ImpactSummaryResponse
from api.routers.ingest import IngestResponse, IngestTextRequest
from api.routers.query import ComplianceQueryRequest, ComplianceQueryResponse
from aria.contracts import impact as impact_contracts
from aria.contracts import regulation as regulation_contracts
from aria.contracts.agent_messages import TaskEnvelope, TaskStatus
from aria.contracts.graph_entities import GraphWritePayload, GraphWriteStatus
from aria.contracts.impact import (
    ImpactAnalysisRequest,
    ImpactReport,
    SCHEMA_VERSION as IMPACT_SCHEMA_VERSION,
)
from aria.contracts.regulation import ExtractedEntities, SCHEMA_VERSION as REGULATION_SCHEMA_VERSION
from aria.graph.queries import QUERIES
from aria.protocols.a2a.agent_card import AGENT_CARDS, AgentCard
from aria.protocols.a2a.server import A2AServer
from aria.protocols.mcp.server import MCPServer
from aria.protocols.mcp.tools import (
    TOOL_DEFINITIONS,
    CypherQueryInput,
    HybridRetrievalInput,
    RegulationFetchInput,
    ToolResult,
    VectorSearchInput,
)
from aria.agents.graph_builder import GraphBuilderAgent
from aria.graph.builder import entities_to_write_payload
from tests.fixtures.entities import HAPPY_MINIMAL_SINGLE_CHAIN

client = TestClient(app)

# Column aliases returned by the impact_by_regulation Cypher query (stable contract for consumers).
IMPACT_BY_REGULATION_ROW_KEYS = frozenset(
    {
        "regulation",
        "article",
        "article_id",
        "requirement_id",
        "requirement",
        "obligation_type",
        "system_id",
        "system_name",
        "team",
        "team_id",
        "policy_id",
        "policy_title",
    }
)

# Declared schema names on agent cards must map to importable Pydantic models where applicable.
_SCHEMA_NAME_TO_MODEL: dict[str, type[BaseModel]] = {
    "ExtractedEntities": ExtractedEntities,
    "GraphWriteStatus": GraphWriteStatus,
    "ImpactAnalysisRequest": ImpactAnalysisRequest,
    "ImpactReport": ImpactReport,
}


class TestAPIResponseShapes:
    """Router responses validate against declared Pydantic response models."""

    def test_health_returns_object(self) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body.get("status") == "healthy"

    def test_ready_returns_dependency_shape(self) -> None:
        r = client.get("/ready")
        assert r.status_code in (200, 503)
        body = r.json()
        assert body.get("service") == "aria-api"
        assert body.get("status") in ("ready", "degraded")
        assert body.get("neo4j") in (True, False)
        assert body.get("chroma") in (True, False)
        if r.status_code == 200:
            assert body.get("status") == "ready"
            assert body["neo4j"] is True and body["chroma"] is True
        else:
            assert body.get("status") == "degraded"

    def test_ingest_text_response_model(self) -> None:
        r = client.post(
            "/ingest/text",
            json=IngestTextRequest(text="Article 1. Test body.", source="eval").model_dump(),
        )
        assert r.status_code == 200
        IngestResponse.model_validate(r.json())

    def test_query_response_model(self) -> None:
        r = client.post(
            "/query",
            json=ComplianceQueryRequest(question="What applies to ML?").model_dump(),
        )
        assert r.status_code == 200
        ComplianceQueryResponse.model_validate(r.json())

    def test_impact_response_model(self) -> None:
        r = client.get("/impact/reg-eval-1")
        assert r.status_code == 200
        ImpactSummaryResponse.model_validate(r.json())

    def test_agents_list_items_match_agent_card_schema(self) -> None:
        r = client.get("/agents")
        assert r.status_code == 200
        for item in r.json():
            AgentCard.model_validate(item)


class TestAPIErrorFormat:
    """Errors use FastAPI/Starlette JSON bodies, not raw exception strings."""

    def test_ingest_empty_text_400_with_detail(self) -> None:
        r = client.post("/ingest/text", json={"text": "   "})
        assert r.status_code == 400
        body = r.json()
        assert "detail" in body
        assert isinstance(body["detail"], str)

    def test_agent_not_found_404_with_detail(self) -> None:
        r = client.get("/agents/does-not-exist")
        assert r.status_code == 404
        body = r.json()
        assert "detail" in body


class TestPlaceholderEndpointsDocumented:
    """Placeholder behavior is visible in endpoint docstrings (API consumers)."""

    @pytest.mark.parametrize(
        "endpoint",
        [
            query_router.compliance_query,
            impact_router.get_impact_report,
        ],
    )
    def test_docstring_mentions_placeholder(self, endpoint: Any) -> None:
        doc = inspect.getdoc(endpoint) or ""
        assert "placeholder" in doc.lower(), f"{endpoint.__name__} should document placeholder"


class TestExtractedEntitiesPipeline:
    """ExtractedEntities → graph payload → graph builder input validation."""

    def test_entities_to_write_payload_produces_valid_graph_write_payload(self) -> None:
        payload = entities_to_write_payload(HAPPY_MINIMAL_SINGLE_CHAIN)
        GraphWritePayload.model_validate(payload.model_dump())

    @pytest.mark.asyncio
    async def test_graph_builder_accepts_extractor_output_dict(self) -> None:
        agent = GraphBuilderAgent(neo4j_client=None)
        data = HAPPY_MINIMAL_SINGLE_CHAIN.model_dump()
        out = await agent.process(data)
        assert isinstance(out, dict)
        assert "nodes_created" in out or "errors" in out


class TestImpactReportVsImpactByRegulationQuery:
    """ImpactReport (agent contract) vs graph rows (impact_by_regulation) — shape docs."""

    def test_impact_by_regulation_row_keys_stable(self) -> None:
        """RETURN aliases are the integration surface for MCP/graph_query consumers."""
        q = QUERIES["impact_by_regulation"]
        assert q.name == "impact_by_regulation"
        for key in IMPACT_BY_REGULATION_ROW_KEYS:
            assert f" AS {key}" in q.cypher or f" AS {key}\n" in q.cypher, key

    def test_impact_summary_api_is_not_impact_report_model(self) -> None:
        """HTTP summary is a separate, flatter DTO; full analysis uses ImpactReport."""
        summary_fields = set(ImpactSummaryResponse.model_fields)
        report_fields = set(ImpactReport.model_fields)
        assert summary_fields != report_fields
        assert "details" in summary_fields
        assert "remediation_tasks" in report_fields
        assert "affected_systems" in report_fields

    @pytest.mark.asyncio
    async def test_impact_analyzer_maps_query_rows_to_impact_report(self) -> None:
        """impact_by_regulation row shape is consumed by ImpactAnalyzerAgent → ImpactReport."""
        from aria.agents.impact_analyzer import ImpactAnalyzerAgent

        row = {k: None for k in IMPACT_BY_REGULATION_ROW_KEYS}
        row.update(
            {
                "regulation": "Test Regulation",
                "article": "5",
                "article_id": "art-5",
                "requirement_id": "req-1",
                "requirement": "Retain logs",
                "obligation_type": "record_keeping",
                "system_id": "sys-1",
                "system_name": "Log Store",
                "team": "Platform",
                "team_id": "team-plat",
                "policy_id": None,
                "policy_title": None,
            }
        )
        agent = ImpactAnalyzerAgent(graph_query_fn=None)
        out = await agent.process({"regulation_id": "reg-test", "impact_data": [row]})
        ImpactReport.model_validate(out)


class TestA2ATaskEnvelopeAndRegistry:
    """Agent cards exposed by /agents align with AGENT_CARDS; TaskEnvelope lifecycle."""

    def test_list_agents_matches_registry_cards(self) -> None:
        r = client.get("/agents")
        assert r.status_code == 200
        listed = {c["name"]: AgentCard.model_validate(c) for c in r.json()}
        assert len(listed) == len(AGENT_CARDS)
        for key, card in AGENT_CARDS.items():
            by_route = client.get(f"/agents/{key}")
            assert by_route.status_code == 200
            assert by_route.json()["agent_id"] == card.agent_id

    def test_agent_card_schema_names_resolve_when_not_dict(self) -> None:
        """Cards that name a Pydantic model should use a known contract (dict is generic)."""
        for card in AGENT_CARDS.values():
            for field in (card.input_schema, card.output_schema):
                if field in ("dict", ""):
                    continue
                assert field in _SCHEMA_NAME_TO_MODEL, (
                    f"Agent {card.agent_id} references unknown schema {field!r}"
                )

    @pytest.mark.asyncio
    async def test_a2a_server_task_envelope_roundtrip(self) -> None:
        card = AGENT_CARDS["entity_extractor"]

        async def handler(payload: dict[str, Any]) -> dict[str, Any]:
            ExtractedEntities.model_validate(payload)
            return {"ok": True}

        server = A2AServer(card, handler)
        envelope = TaskEnvelope(
            source_agent="supervisor",
            target_agent=card.agent_id,
            task_type="entity_extraction",
            input_payload=HAPPY_MINIMAL_SINGLE_CHAIN.model_dump(),
        )
        out = await server._process_task(envelope)
        assert out.status == TaskStatus.COMPLETED
        assert out.output_payload == {"ok": True}


class TestMCPToolContract:
    """list_tools metadata matches handler input models; call_tool validates arguments."""

    def test_list_tools_schemas_match_pydantic_json_schema(self) -> None:
        expected = {
            "graph_query": CypherQueryInput.model_json_schema(),
            "vector_search": VectorSearchInput.model_json_schema(),
            "hybrid_retrieve": HybridRetrievalInput.model_json_schema(),
            "fetch_regulation": RegulationFetchInput.model_json_schema(),
        }
        by_name = {t.name: t for t in TOOL_DEFINITIONS}
        assert set(by_name) == set(expected)
        out_schema = ToolResult.model_json_schema()
        for name, schema in expected.items():
            assert by_name[name].input_schema == schema
            assert by_name[name].output_schema == out_schema

    @pytest.mark.asyncio
    async def test_call_tool_unknown_tool_returns_structured_error(self) -> None:
        mcp = MCPServer(neo4j_client=None, vector_store=None)
        result = await mcp.call_tool("no_such_tool", {})
        assert isinstance(result, ToolResult)
        assert result.success is False
        assert result.error
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_call_tool_validates_graph_query_input(self) -> None:
        mcp = MCPServer(neo4j_client=None, vector_store=None)
        result = await mcp.call_tool("graph_query", {})
        assert result.success is False
        assert result.error

    @pytest.mark.asyncio
    async def test_call_tool_graph_query_success_shape(self) -> None:
        class _StubNeo4j:
            async def execute_read(
                self,
                query: str,
                parameters: dict[str, Any] | None = None,
                database: str = "neo4j",
            ) -> list[dict[str, Any]]:
                return [{"stub": True}]

        mcp = MCPServer(neo4j_client=_StubNeo4j(), vector_store=None)
        result = await mcp.call_tool(
            "graph_query",
            {"query_name": "list_regulations", "parameters": {}},
        )
        assert result.success is True
        assert result.tool_name == "graph_query"
        assert result.data == [{"stub": True}]


class TestSchemaVersioning:
    """SCHEMA_VERSION constants are embedded in models but not enforced at runtime."""

    def test_contract_models_default_schema_version(self) -> None:
        assert regulation_contracts.SCHEMA_VERSION == "0.1.0"
        assert impact_contracts.SCHEMA_VERSION == "0.1.0"
        entities = ExtractedEntities(
            source_document_hash="h",
            schema_version=REGULATION_SCHEMA_VERSION,
        )
        assert entities.schema_version == "0.1.0"
        report = ImpactReport(regulation_id="r", regulation_title="T")
        assert report.schema_version == IMPACT_SCHEMA_VERSION

    def test_client_may_send_different_schema_version_value(self) -> None:
        """No server-side check rejects unknown versions; value is stored as sent."""
        payload = HAPPY_MINIMAL_SINGLE_CHAIN.model_dump()
        payload["schema_version"] = "99.0.0"
        loaded = ExtractedEntities.model_validate(payload)
        assert loaded.schema_version == "99.0.0"

    def test_schema_version_not_asserted_in_codebase(self) -> None:
        """Document: SCHEMA_VERSION is informational unless callers add checks."""
        # If this fails, update the test — a global version gate was added.
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        hits: list[str] = []
        for path in root.joinpath("aria").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "schema_version" in text and "SCHEMA_VERSION" in text:
                if "assert" in text and "schema_version" in text:
                    hits.append(str(path))
        assert not hits, f"Unexpected schema_version assertions: {hits}"


def test_openapi_includes_core_paths() -> None:
    schema = app.openapi()
    paths = schema.get("paths", {})
    assert "/health" in paths
    assert "/ready" in paths
    assert "/ingest/text" in paths
    assert "/query" in paths
    for route in agents_router.routes:
        path = getattr(route, "path", None)
        if path:
            openapi_path = path.replace("{agent_name}", "{agent_name}")
            assert openapi_path in paths or path in paths
