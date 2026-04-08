"""Conditional edge logic for the scratch orchestration engine.

Each edge function takes the current state and returns the name of
the next node. This is the routing table for the orchestration graph.

``gap_analysis`` (``regulation_id`` + ``query``, no document) and
``impact_query`` (``regulation_id`` only) share the same branch:
``is_impact_query`` is true whenever ``regulation_id`` is set and there is
no ``raw_document``. The scratch graph does not introduce a separate
gap-analysis node yet; see ``SupervisorAgent`` docstring.
"""

from __future__ import annotations

from typing import Callable

from aria.orchestration.scratch.state import ARIAState

EdgeFunction = Callable[[ARIAState], str]


def route_after_supervisor(state: ARIAState) -> str:
    if state.has_error:
        return "end"
    if state.is_ingestion_request:
        return "ingestion"
    if state.is_free_query:
        return "free_query"
    if state.is_impact_query:
        return "impact_analyzer"
    return "end"


def route_after_ingestion(state: ARIAState) -> str:
    if state.has_error:
        return "end"
    return "entity_extractor"


def route_after_entity_extractor(state: ARIAState) -> str:
    if state.has_error:
        return "end"
    if state.extracted_entities:
        return "graph_builder"
    return "end"


def route_after_free_query(state: ARIAState) -> str:
    return "end"


def route_after_graph_builder(state: ARIAState) -> str:
    if state.has_error:
        return "end"
    if state.regulation_id:
        return "impact_analyzer"
    return "end"


def route_after_impact_analyzer(state: ARIAState) -> str:
    if state.has_error:
        return "end"
    if state.impact_report:
        return "report_generator"
    return "end"


def route_after_report_generator(state: ARIAState) -> str:
    return "end"


EDGE_MAP: dict[str, EdgeFunction] = {
    "supervisor": route_after_supervisor,
    "ingestion": route_after_ingestion,
    "entity_extractor": route_after_entity_extractor,
    "free_query": route_after_free_query,
    "graph_builder": route_after_graph_builder,
    "impact_analyzer": route_after_impact_analyzer,
    "report_generator": route_after_report_generator,
}
