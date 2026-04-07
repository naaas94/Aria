"""Node definitions for the scratch orchestration engine.

Each node is a callable: (state: ARIAState, tools: ToolPorts) -> ARIAState.
Nodes perform a single unit of work and return updated state.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from aria.orchestration.scratch.state import ARIAState

logger = logging.getLogger(__name__)


class ToolPorts(Protocol):
    """MCP-shaped tool interface. Agents program against this contract;
    Phase 5 wires it to real MCP transport."""

    async def extract_entities(self, text: str, doc_hash: str) -> dict: ...
    async def write_to_graph(self, entities: dict) -> dict: ...
    async def index_vectors(self, chunks: list[dict]) -> bool: ...
    async def query_graph(self, query_name: str, params: dict) -> list[dict]: ...
    async def vector_search(self, query: str, top_k: int) -> list[dict]: ...
    async def generate_text(self, messages: list[dict]) -> str: ...


async def supervisor_node(state: "ARIAState", tools: ToolPorts) -> "ARIAState":
    """Route based on what's in state: ingestion, impact query, free query, or end."""
    state.record_step("supervisor")
    logger.info("Supervisor: classifying intent")

    if state.has_error:
        logger.error("Supervisor: error state detected — routing to end")
    elif state.is_ingestion_request:
        logger.info("Supervisor: routing to ingestion pipeline")
    elif state.is_impact_query:
        logger.info("Supervisor: routing to impact analyzer")
    elif state.is_free_query:
        logger.info("Supervisor: routing to free query (vector search)")
    else:
        logger.info("Supervisor: no actionable input — routing to end")

    return state


async def ingestion_node(state: "ARIAState", tools: ToolPorts) -> "ARIAState":
    """Validate ingest input; entity extraction runs in ``entity_extractor_node``."""
    state.record_step("ingestion")
    logger.info("Ingestion: validating document for extraction pipeline")

    if not state.raw_document:
        state.error = "Ingestion node received no raw_document"
        return state

    return state


async def free_query_node(state: "ARIAState", tools: ToolPorts) -> "ARIAState":
    """Ad-hoc questions via vector search (no regulation_id required)."""
    state.record_step("free_query")
    logger.info("Free query: vector search")

    q = (state.query or "").strip()
    if not q:
        state.error = "Free query node received no query"
        return state

    try:
        hits = await tools.vector_search(q, top_k=8)
        if not hits:
            state.final_report = (
                "No vector matches were returned for this query. "
                "Ensure documents are indexed or rephrase the question."
            )
        else:
            lines: list[str] = []
            for i, h in enumerate(hits, 1):
                snippet = h.get("text") or h.get("content") or str(h)
                lines.append(f"{i}. {snippet[:500]}")
            state.final_report = "\n".join(lines)
    except Exception as exc:
        state.error = f"Vector search failed: {exc}"
        logger.error(state.error)

    return state


async def entity_extractor_node(state: "ARIAState", tools: ToolPorts) -> "ARIAState":
    """Dedicated entity extraction step (when separated from ingestion)."""
    state.record_step("entity_extractor")

    if not state.raw_document:
        state.error = "Entity extractor received no document"
        return state

    try:
        result = await tools.extract_entities(
            state.raw_document, state.document_hash or "unknown"
        )
        from aria.contracts.regulation import ExtractedEntities
        state.extracted_entities = ExtractedEntities.model_validate(result)
        logger.info(
            "Entity extractor: extracted %d regulations",
            len(state.extracted_entities.regulations),
        )
    except Exception as exc:
        state.error = f"Entity extraction failed: {exc}"

    return state


async def graph_builder_node(state: "ARIAState", tools: ToolPorts) -> "ARIAState":
    """Write extracted entities to the knowledge graph."""
    state.record_step("graph_builder")

    if not state.extracted_entities:
        state.error = "Graph builder received no extracted entities"
        return state

    try:
        result = await tools.write_to_graph(state.extracted_entities.model_dump())
        from aria.contracts.graph_entities import GraphWriteStatus
        state.graph_write_status = GraphWriteStatus.model_validate(result)

        if not state.graph_write_status.success:
            state.error = f"Graph write errors: {state.graph_write_status.errors}"
    except Exception as exc:
        state.error = f"Graph write failed: {exc}"

    return state


async def impact_analyzer_node(state: "ARIAState", tools: ToolPorts) -> "ARIAState":
    """Run multi-hop impact analysis via graph queries."""
    state.record_step("impact_analyzer")

    if not state.regulation_id:
        state.error = "Impact analyzer received no regulation_id"
        return state

    try:
        impact_rows = await tools.query_graph(
            "impact_by_regulation", {"regulation_id": state.regulation_id}
        )

        from aria.contracts.impact import (
            AffectedAsset,
            CoverageStatus,
            ImpactReport,
        )

        affected: list[AffectedAsset] = []
        coverage_counts: dict[CoverageStatus, int] = {s: 0 for s in CoverageStatus}

        for row in impact_rows:
            status = CoverageStatus.COVERED if row.get("policy_id") else CoverageStatus.GAP
            coverage_counts[status] = coverage_counts.get(status, 0) + 1
            affected.append(
                AffectedAsset(
                    system_id=row.get("system_id", ""),
                    system_name=row.get("system_name", ""),
                    owner_team=row.get("team", ""),
                    requirement_id=row.get("requirement_id", ""),
                    requirement_text=row.get("requirement", ""),
                    coverage_status=status,
                    covering_policy_id=row.get("policy_id"),
                    covering_policy_title=row.get("policy_title"),
                )
            )

        state.impact_report = ImpactReport(
            regulation_id=state.regulation_id,
            regulation_title=impact_rows[0].get("regulation", "") if impact_rows else "",
            total_requirements=len(impact_rows),
            affected_systems=affected,
            coverage_summary=coverage_counts,
        )
        logger.info(
            "Impact analysis complete: %d affected assets, %d gaps",
            len(affected), state.impact_report.gap_count,
        )
    except Exception as exc:
        state.error = f"Impact analysis failed: {exc}"

    return state


async def report_generator_node(state: "ARIAState", tools: ToolPorts) -> "ARIAState":
    """Generate a human-readable compliance report from the impact analysis."""
    state.record_step("report_generator")

    if not state.impact_report:
        state.error = "Report generator received no impact report"
        return state

    try:
        prompt = (
            f"Generate a compliance report for {state.impact_report.regulation_title}.\n"
            f"Total requirements: {state.impact_report.total_requirements}\n"
            f"Gaps found: {state.impact_report.gap_count}\n"
            f"Risk level: {state.impact_report.risk_level}\n\n"
            f"Affected systems:\n"
        )
        for asset in state.impact_report.affected_systems:
            prompt += (
                f"- {asset.system_name} ({asset.owner_team}): "
                f"{asset.coverage_status} — {asset.requirement_text}\n"
            )

        state.final_report = await tools.generate_text(
            [{"role": "user", "content": prompt}]
        )
    except Exception as exc:
        state.error = f"Report generation failed: {exc}"

    return state


async def end_node(state: "ARIAState", tools: ToolPorts) -> "ARIAState":
    """Terminal node — marks the orchestration run as complete."""
    state.record_step("end")
    logger.info("Orchestration complete. Steps: %s", " -> ".join(state.history))
    return state
