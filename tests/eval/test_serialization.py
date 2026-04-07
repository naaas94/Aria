"""JSON serialization roundtrips for Pydantic contracts and protocol models.

Ensures domain models, MCP tool I/O, and agent envelopes survive
``model_dump_json`` / ``model_validate_json`` without structural loss.
Date and StrEnum values must roundtrip as JSON-safe primitives.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any

import pytest
from pydantic import BaseModel

from aria.agents.base import AgentResult
from aria.contracts.agent_messages import (
    AgentMessage,
    MessageType,
    TaskEnvelope,
    TaskStatus,
)
from aria.contracts.graph_entities import (
    EdgeType,
    GraphEdge,
    GraphNode,
    GraphQueryResult,
    GraphWritePayload,
    GraphWriteStatus,
    NodeLabel,
)
from aria.contracts.impact import (
    AffectedAsset,
    CoverageStatus,
    ImpactAnalysisRequest,
    ImpactReport,
    RemediationTask,
    RiskLevel,
)
from aria.contracts.regulation import (
    Article,
    Deadline,
    DeadlineType,
    ExtractedEntities,
    InternalSystem,
    Jurisdiction,
    ObligationType,
    PolicyDocument,
    Regulation,
    Requirement,
    Team,
)
from aria.protocols.a2a.agent_card import AgentCard
from aria.protocols.mcp.tools import (
    CypherQueryInput,
    HybridRetrievalInput,
    RegulationFetchInput,
    ToolDefinition,
    ToolResult,
    VectorSearchInput,
)
from tests.fixtures.entities import HAPPY_MINIMAL_SINGLE_CHAIN


def _assert_json_roundtrip(model_cls: type[BaseModel], instance: BaseModel) -> None:
    """Serialize to JSON and parse back; compare canonical JSON-ready payloads."""
    dumped = instance.model_dump(mode="json")
    json_str = json.dumps(dumped)
    loaded = json.loads(json_str)
    restored = model_cls.model_validate(loaded)
    assert restored.model_dump(mode="json") == dumped


def _assert_model_json_roundtrip(model_cls: type[BaseModel], instance: BaseModel) -> None:
    """Use Pydantic's native JSON helpers (must match manual JSON path)."""
    restored = model_cls.model_validate_json(instance.model_dump_json())
    assert restored.model_dump(mode="json") == instance.model_dump(mode="json")


@pytest.mark.parametrize(
    "model_cls,factory",
    [
        (
            Jurisdiction,
            lambda: Jurisdiction(id="eu", name="European Union", region="EU"),
        ),
        (
            Deadline,
            lambda: Deadline(
                id="dl-1",
                date=date(2026, 5, 1),
                type=DeadlineType.COMPLIANCE,
                article_id="art-1",
                description="Compliance deadline",
            ),
        ),
        (
            Requirement,
            lambda: Requirement(
                id="req-1",
                text="Process personal data lawfully.",
                obligation_type=ObligationType.REQUIREMENT,
                deadline=date(2026, 6, 1),
                description="",
            ),
        ),
        (
            Article,
            lambda: Article(
                id="art-1",
                number="5",
                title="Principles",
                text_summary="Summary",
                regulation_id="reg-1",
                requirements=[
                    Requirement(
                        id="req-a",
                        text="Requirement text",
                        obligation_type=ObligationType.PROHIBITION,
                    )
                ],
                deadlines=[
                    Deadline(
                        id="dl-a",
                        date=date(2026, 1, 15),
                        type=DeadlineType.REPORTING,
                        article_id="art-1",
                    )
                ],
            ),
        ),
        (
            Regulation,
            lambda: Regulation(
                id="reg-1",
                title="Example Regulation",
                jurisdiction="eu",
                domain="privacy",
                effective_date=date(2026, 1, 1),
                source_url="https://example.invalid/reg",
                articles=[],
                amends=["reg-old"],
                references=["reg-related"],
            ),
        ),
        (
            PolicyDocument,
            lambda: PolicyDocument(
                id="pol-1",
                title="Data Policy",
                owner_team="team-1",
                version="2.0",
                last_reviewed=date(2026, 3, 1),
            ),
        ),
        (
            InternalSystem,
            lambda: InternalSystem(
                id="sys-1",
                name="CRM",
                description="Customer DB",
                category="Sales",
                owner_team="team-1",
                data_types=["pii"],
            ),
        ),
        (Team, lambda: Team(id="team-1", name="Compliance", function="GRC", contact="c@x")),
    ],
)
def test_regulation_module_roundtrip(
    model_cls: type[BaseModel], factory: Callable[[], BaseModel]
) -> None:
    instance = factory()
    _assert_json_roundtrip(model_cls, instance)
    _assert_model_json_roundtrip(model_cls, instance)


def test_extracted_entities_fixture_roundtrip() -> None:
    _assert_json_roundtrip(ExtractedEntities, HAPPY_MINIMAL_SINGLE_CHAIN)
    _assert_model_json_roundtrip(ExtractedEntities, HAPPY_MINIMAL_SINGLE_CHAIN)


@pytest.mark.parametrize(
    "model_cls,factory",
    [
        (
            ImpactAnalysisRequest,
            lambda: ImpactAnalysisRequest(regulation_id="reg-gdpr"),
        ),
        (
            AffectedAsset,
            lambda: AffectedAsset(
                system_id="sys-1",
                system_name="CRM",
                owner_team="team-1",
                requirement_id="req-1",
                requirement_text="Do X",
                coverage_status=CoverageStatus.GAP,
                covering_policy_id=None,
                covering_policy_title=None,
            ),
        ),
        (
            RemediationTask,
            lambda: RemediationTask(
                id="task-1",
                title="Fix gap",
                description="Implement control",
                priority=RiskLevel.HIGH,
                assigned_team="team-1",
                deadline=date(2026, 12, 31),
                requirement_id="req-1",
                system_id="sys-1",
            ),
        ),
        (
            ImpactReport,
            lambda: ImpactReport(
                regulation_id="reg-1",
                regulation_title="GDPR",
                total_requirements=10,
                affected_systems=[],
                remediation_tasks=[],
                coverage_summary={CoverageStatus.GAP: 2, CoverageStatus.COVERED: 8},
            ),
        ),
    ],
)
def test_impact_module_roundtrip(
    model_cls: type[BaseModel], factory: Callable[[], BaseModel]
) -> None:
    instance = factory()
    _assert_json_roundtrip(model_cls, instance)
    _assert_model_json_roundtrip(model_cls, instance)


@pytest.mark.parametrize(
    "model_cls,factory",
    [
        (
            GraphNode,
            lambda: GraphNode(
                label=NodeLabel.REQUIREMENT,
                properties={
                    "id": "req-1",
                    "text": "t",
                    "obligation_type": "requirement",
                    "description": "",
                },
            ),
        ),
        (
            GraphEdge,
            lambda: GraphEdge(
                source_label=NodeLabel.ARTICLE,
                source_id="a1",
                target_label=NodeLabel.REQUIREMENT,
                target_id="r1",
                edge_type=EdgeType.IMPOSES,
                properties={},
            ),
        ),
        (
            GraphWritePayload,
            lambda: GraphWritePayload(
                nodes=[
                    GraphNode(label=NodeLabel.TEAM, properties={"id": "t1", "name": "T"})
                ],
                edges=[],
            ),
        ),
        (
            GraphWriteStatus,
            lambda: GraphWriteStatus(
                nodes_created=1,
                nodes_merged=2,
                edges_created=3,
                edges_merged=4,
                errors=["e1"],
            ),
        ),
        (
            GraphQueryResult,
            lambda: GraphQueryResult(
                columns=["a", "b"],
                rows=[{"a": 1, "b": "x"}],
                query_time_ms=1.5,
            ),
        ),
    ],
)
def test_graph_entities_roundtrip(
    model_cls: type[BaseModel], factory: Callable[[], BaseModel]
) -> None:
    instance = factory()
    _assert_json_roundtrip(model_cls, instance)
    _assert_model_json_roundtrip(model_cls, instance)


@pytest.mark.parametrize(
    "model_cls,factory",
    [
        (
            AgentMessage,
            lambda: AgentMessage(
                message_type=MessageType.REQUEST,
                source_agent="a",
                target_agent="b",
                payload={"k": 1},
                correlation_id="cid-1",
            ),
        ),
        (
            TaskEnvelope,
            lambda: TaskEnvelope(
                task_id="fixed-id",
                status=TaskStatus.PENDING,
                created_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
                updated_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
                source_agent="supervisor",
                target_agent="entity_extractor",
                task_type="entity_extraction",
                input_payload={"document_hash": "abc"},
                output_payload={},
                error_detail=None,
            ),
        ),
    ],
)
def test_agent_messages_roundtrip(
    model_cls: type[BaseModel], factory: Callable[[], BaseModel]
) -> None:
    instance = factory()
    _assert_json_roundtrip(model_cls, instance)
    _assert_model_json_roundtrip(model_cls, instance)


@pytest.mark.parametrize(
    "model_cls,factory",
    [
        (
            AgentCard,
            lambda: AgentCard(
                agent_id="test-01",
                name="Test Agent",
                version="0.1.0",
                description="D",
                capabilities=["c1"],
                input_schema="ExtractedEntities",
                output_schema="GraphWriteStatus",
                endpoint="http://localhost:9/a2a",
                protocol_version="0.1",
            ),
        ),
        (
            CypherQueryInput,
            lambda: CypherQueryInput(
                query_name="list_regulations",
                parameters={},
            ),
        ),
        (
            VectorSearchInput,
            lambda: VectorSearchInput(query_text="privacy", top_k=5),
        ),
        (
            HybridRetrievalInput,
            lambda: HybridRetrievalInput(
                query_text="q",
                vector_top_k=10,
                graph_hops=2,
                node_label_hint="Requirement",
            ),
        ),
        (
            RegulationFetchInput,
            lambda: RegulationFetchInput(regulation_id="reg-1"),
        ),
        (
            ToolResult,
            lambda: ToolResult(
                tool_name="graph_query",
                success=True,
                data=[{"row": 1}],
                error=None,
            ),
        ),
        (
            ToolDefinition,
            lambda: ToolDefinition(
                name="graph_query",
                description="d",
                input_schema={"type": "object", "title": "X"},
            ),
        ),
        (
            AgentResult,
            lambda: AgentResult(
                agent_name="x",
                success=True,
                output={"a": 1},
                error=None,
                duration_ms=12.5,
            ),
        ),
    ],
)
def test_protocol_and_agent_envelope_roundtrip(
    model_cls: type[BaseModel], factory: Callable[[], BaseModel]
) -> None:
    instance = factory()
    _assert_json_roundtrip(model_cls, instance)
    _assert_model_json_roundtrip(model_cls, instance)


def test_str_enum_json_values_are_strings() -> None:
    """StrEnum fields must serialize as JSON strings (portable across boundaries)."""
    req = Requirement(
        id="r",
        text="t",
        obligation_type=ObligationType.NOTIFICATION,
    )
    raw = json.loads(req.model_dump_json())
    assert raw["obligation_type"] == "notification"
    assert isinstance(raw["obligation_type"], str)


def test_date_fields_iso_format_in_json() -> None:
    reg = Regulation(
        id="r",
        title="T",
        jurisdiction="eu",
        domain="d",
        effective_date=date(2026, 4, 7),
    )
    raw = json.loads(reg.model_dump_json())
    assert raw["effective_date"] == "2026-04-07"


def test_datetime_fields_iso_format_in_json() -> None:
    env = TaskEnvelope(
        source_agent="a",
        target_agent="b",
        task_type="t",
        created_at=datetime(2026, 4, 7, 15, 30, 0, tzinfo=timezone.utc),
    )
    raw = json.loads(env.model_dump_json())
    assert raw["created_at"].startswith("2026-04-07")
