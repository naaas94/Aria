"""Pre-built ARIAState instances for orchestration routing and offline tests."""

from __future__ import annotations

from datetime import date

from aria.contracts.graph_entities import GraphWriteStatus
from aria.contracts.impact import (
    AffectedAsset,
    CoverageStatus,
    ImpactReport,
    RemediationTask,
    RiskLevel,
)
from aria.orchestration.scratch.state import ARIAState

from tests.fixtures.documents import GDPR_ARTICLE_5_PLAIN
from tests.fixtures.entities import HAPPY_MINIMAL_SINGLE_CHAIN

# ---------------------------------------------------------------------------
# Entry conditions — happy-style starting points (≥3)
# ---------------------------------------------------------------------------

STATE_ENTRY_INGESTION = ARIAState(
    raw_document=GDPR_ARTICLE_5_PLAIN,
    document_hash="sha256-entry-ingest-demo",
    current_node="supervisor",
    history=["supervisor"],
)

STATE_ENTRY_IMPACT_QUERY = ARIAState(
    regulation_id="reg-gdpr",
    current_node="supervisor",
    history=["supervisor"],
)

STATE_ENTRY_FREE_QUERY = ARIAState(
    query="Which teams own systems affected by GDPR Article 17?",
    current_node="supervisor",
    history=["supervisor"],
)

# ---------------------------------------------------------------------------
# Entry conditions — gap analysis, empty, error (covers remaining entry semantics)
# ---------------------------------------------------------------------------

STATE_ENTRY_GAP_ANALYSIS = ARIAState(
    regulation_id="reg-eu-ai-act",
    query="List uncovered requirements for chatbot transparency and suggest remediation owners.",
    current_node="supervisor",
    history=["supervisor"],
)

STATE_ENTRY_EMPTY = ARIAState()

STATE_ENTRY_ERRORED = ARIAState(
    error="Neo4j connection refused: bolt://localhost:7687",
    current_node="ingestion",
    history=["supervisor", "ingestion"],
)

# ---------------------------------------------------------------------------
# Mid-pipeline states (≥3 distinct stages)
# ---------------------------------------------------------------------------

STATE_MID_POST_INGESTION_AWAITING_EXTRACTION = ARIAState(
    raw_document="stub",
    document_hash="abc123",
    current_node="ingestion",
    history=["supervisor", "ingestion"],
)

STATE_MID_POST_ENTITY_EXTRACTION = ARIAState(
    raw_document="stub",
    document_hash="abc123",
    extracted_entities=HAPPY_MINIMAL_SINGLE_CHAIN,
    current_node="entity_extractor",
    history=["supervisor", "ingestion", "entity_extractor"],
)

STATE_MID_POST_GRAPH_BUILDER = ARIAState(
    raw_document="stub",
    document_hash="abc123",
    extracted_entities=HAPPY_MINIMAL_SINGLE_CHAIN,
    graph_write_status=GraphWriteStatus(
        nodes_created=4,
        nodes_merged=2,
        edges_created=5,
        edges_merged=1,
        errors=[],
    ),
    current_node="graph_builder",
    history=["supervisor", "ingestion", "entity_extractor", "graph_builder"],
)

STATE_MID_POST_IMPACT_ANALYZER = ARIAState(
    regulation_id="reg-gdpr",
    impact_report=ImpactReport(
        regulation_id="reg-gdpr",
        regulation_title="General Data Protection Regulation",
        total_requirements=2,
        affected_systems=[
            AffectedAsset(
                system_id="sys-crm",
                system_name="Customer CRM",
                owner_team="Engineering",
                requirement_id="req-gdpr-5-1",
                requirement_text="Lawful processing",
                coverage_status=CoverageStatus.COVERED,
                covering_policy_id="pol-privacy",
                covering_policy_title="Data Privacy Policy",
            ),
        ],
        remediation_tasks=[],
        coverage_summary={CoverageStatus.COVERED: 1},
    ),
    current_node="impact_analyzer",
    history=["supervisor", "impact_analyzer"],
)

STATE_MID_REPORT_GENERATOR = ARIAState(
    regulation_id="reg-gdpr",
    impact_report=ImpactReport(
        regulation_id="reg-gdpr",
        regulation_title="GDPR",
        total_requirements=1,
        affected_systems=[
            AffectedAsset(
                system_id="sys-x",
                system_name="System X",
                owner_team="Team Y",
                requirement_id="req-1",
                requirement_text="Requirement",
                coverage_status=CoverageStatus.GAP,
            ),
        ],
        remediation_tasks=[
            RemediationTask(
                id="task-1",
                title="Address gap",
                description="Close the gap",
                priority=RiskLevel.HIGH,
                assigned_team="team-legal",
                deadline=date(2026, 12, 31),
                requirement_id="req-1",
                system_id="sys-x",
            ),
        ],
        coverage_summary={CoverageStatus.GAP: 1},
    ),
    final_report=None,
    current_node="report_generator",
    history=["supervisor", "impact_analyzer", "report_generator"],
)

# ---------------------------------------------------------------------------
# Adversarial / edge states (≥5)
# ---------------------------------------------------------------------------

STATE_ADV_CONFLICTING_INPUTS = ARIAState(
    raw_document="Document present",
    regulation_id="reg-gdpr",
    query="Also a free-form query",
    document_hash="conflict-hash",
)

STATE_ADV_WHITESPACE_ONLY_DOCUMENT = ARIAState(
    raw_document="   \n\t  ",
    document_hash="whitespace",
)

STATE_ADV_STUCK_LOOP_HINT = ARIAState(
    regulation_id="reg-1",
    current_node="entity_extractor",
    history=["supervisor", "entity_extractor"] * 4,
)

STATE_ADV_GRAPH_PARTIAL_FAILURE = ARIAState(
    extracted_entities=HAPPY_MINIMAL_SINGLE_CHAIN,
    graph_write_status=GraphWriteStatus(
        nodes_created=1,
        errors=["Edge write failed (Requirement-[AFFECTS]->InternalSystem): node not found"],
    ),
    current_node="graph_builder",
)

STATE_ADV_COMPLETED_WITH_ERROR_FLAG = ARIAState(
    error="Deprecated: pipeline completed but flagged validation warnings",
    final_report="Report text still produced.",
    current_node="end",
    history=["supervisor", "end"],
)

STATE_ADV_UNKNOWN_NODE_POINTER = ARIAState(
    current_node="nonexistent_node_xyz",
    history=["supervisor", "nonexistent_node_xyz"],
)
