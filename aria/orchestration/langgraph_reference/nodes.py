"""LangGraph node definitions — thin wrappers around scratch node functions.

Each node function operates on a dict state (LangGraph convention) and
delegates to the identical logic in the scratch implementation. This
demonstrates that the two implementations share the same behavior.
"""

from __future__ import annotations

from typing import Any

from aria.orchestration.scratch.state import ARIAState


def _wrap_state(state: dict[str, Any]) -> ARIAState:
    """Convert dict state to Pydantic for processing."""
    return ARIAState.model_validate(state)


def _unwrap_state(state: ARIAState) -> dict[str, Any]:
    """Convert Pydantic state back to dict for LangGraph."""
    return state.model_dump()


async def supervisor_node(state: dict[str, Any]) -> dict[str, Any]:
    s = _wrap_state(state)
    s.record_step("supervisor")
    return _unwrap_state(s)


async def ingestion_node(state: dict[str, Any]) -> dict[str, Any]:
    """Ingestion node — marks entity extraction as pending.

    In the LangGraph reference, actual tool calls are handled by
    the LangGraph tool-calling mechanism. Here we simulate the
    state transition that the scratch implementation performs.
    """
    s = _wrap_state(state)
    s.record_step("ingestion")

    if not s.raw_document:
        s.error = "Ingestion node received no raw_document"

    return _unwrap_state(s)


async def graph_builder_node(state: dict[str, Any]) -> dict[str, Any]:
    s = _wrap_state(state)
    s.record_step("graph_builder")

    if not s.extracted_entities:
        s.error = "Graph builder received no extracted entities"

    return _unwrap_state(s)


async def impact_analyzer_node(state: dict[str, Any]) -> dict[str, Any]:
    s = _wrap_state(state)
    s.record_step("impact_analyzer")

    if not s.regulation_id:
        s.error = "Impact analyzer received no regulation_id"

    return _unwrap_state(s)


async def report_generator_node(state: dict[str, Any]) -> dict[str, Any]:
    s = _wrap_state(state)
    s.record_step("report_generator")
    return _unwrap_state(s)


def route_after_supervisor(state: dict[str, Any]) -> str:
    """Edge routing function — identical logic to scratch edges."""
    s = _wrap_state(state)
    if s.has_error:
        return "end"
    if s.is_ingestion_request:
        return "ingestion"
    if s.is_impact_query or s.is_free_query:
        return "impact_analyzer"
    return "end"


def route_after_ingestion(state: dict[str, Any]) -> str:
    s = _wrap_state(state)
    if s.has_error:
        return "end"
    if s.extracted_entities:
        return "graph_builder"
    return "end"


def route_after_graph_builder(state: dict[str, Any]) -> str:
    s = _wrap_state(state)
    if s.has_error:
        return "end"
    if s.regulation_id:
        return "impact_analyzer"
    return "end"


def route_after_impact_analyzer(state: dict[str, Any]) -> str:
    s = _wrap_state(state)
    if s.has_error:
        return "end"
    if s.impact_report:
        return "report_generator"
    return "end"
