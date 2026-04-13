"""LangGraph node definitions — thin wrappers around scratch behavior.

Routing functions delegate to ``aria.orchestration.scratch.edges`` so the
reference graph stays aligned with the scratch engine. Node bodies remain
lightweight stubs (no real MCP); for full tool behavior use the scratch
``OrchestrationGraph`` with real ``ToolPorts``.
"""

from __future__ import annotations

from typing import Any, cast

from aria.contracts.regulation import ExtractedEntities
from aria.orchestration.langgraph_reference.state import ARIAStateDict
from aria.orchestration.scratch import edges as scratch_edges
from aria.orchestration.scratch.nodes import ToolPorts
from aria.orchestration.scratch.state import ARIAState


class _NoopTools(ToolPorts):
    """Supervisor/ingestion nodes do not call tools; satisfies the protocol."""

    async def extract_entities(self, text: str, doc_hash: str) -> dict[str, Any]:
        raise NotImplementedError

    async def write_to_graph(self, entities: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def index_vectors(self, chunks: list[dict[str, Any]]) -> bool:
        raise NotImplementedError

    async def query_graph(self, query_name: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def vector_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def generate_text(self, messages: list[dict[str, Any]]) -> str:
        raise NotImplementedError


def _wrap_state(state: ARIAStateDict) -> ARIAState:
    """Convert dict state to Pydantic for processing."""
    return ARIAState.model_validate(state)


def _unwrap_state(state: ARIAState) -> ARIAStateDict:
    """Convert Pydantic state back to dict for LangGraph."""
    return cast(ARIAStateDict, state.model_dump())


async def supervisor_node(state: ARIAStateDict) -> ARIAStateDict:
    from aria.orchestration.scratch.nodes import supervisor_node as _sn

    s = _wrap_state(state)
    out = await _sn(s, _NoopTools())
    return _unwrap_state(out)


async def ingestion_node(state: ARIAStateDict) -> ARIAStateDict:
    from aria.orchestration.scratch.nodes import ingestion_node as _in

    s = _wrap_state(state)
    out = await _in(s, _NoopTools())
    return _unwrap_state(out)


async def entity_extractor_node(state: ARIAStateDict) -> ARIAStateDict:
    """Stub extraction — sets minimal ``ExtractedEntities`` when a document exists."""
    s = _wrap_state(state)
    s.record_step("entity_extractor")
    if not s.raw_document:
        s.error = "Entity extractor received no document"
        return _unwrap_state(s)
    s.extracted_entities = ExtractedEntities(
        source_document_hash=s.document_hash or "unknown",
        regulations=[],
    )
    return _unwrap_state(s)


async def free_query_node(state: ARIAStateDict) -> ARIAStateDict:
    s = _wrap_state(state)
    s.record_step("free_query")
    q = (s.query or "").strip()
    if not q:
        s.error = "Free query node received no query"
    else:
        s.final_report = "[LangGraph reference stub] No vector index wired."
    return _unwrap_state(s)


async def graph_builder_node(state: ARIAStateDict) -> ARIAStateDict:
    s = _wrap_state(state)
    s.record_step("graph_builder")

    if not s.extracted_entities:
        s.error = "Graph builder received no extracted entities"

    return _unwrap_state(s)


async def impact_analyzer_node(state: ARIAStateDict) -> ARIAStateDict:
    s = _wrap_state(state)
    s.record_step("impact_analyzer")

    if not s.regulation_id:
        s.error = "Impact analyzer received no regulation_id"

    return _unwrap_state(s)


async def report_generator_node(state: ARIAStateDict) -> ARIAStateDict:
    s = _wrap_state(state)
    s.record_step("report_generator")
    return _unwrap_state(s)


def route_after_supervisor(state: ARIAStateDict) -> str:
    return scratch_edges.route_after_supervisor(ARIAState.model_validate(state))


def route_after_ingestion(state: ARIAStateDict) -> str:
    return scratch_edges.route_after_ingestion(ARIAState.model_validate(state))


def route_after_entity_extractor(state: ARIAStateDict) -> str:
    return scratch_edges.route_after_entity_extractor(ARIAState.model_validate(state))


def route_after_free_query(state: ARIAStateDict) -> str:
    return scratch_edges.route_after_free_query(ARIAState.model_validate(state))


def route_after_graph_builder(state: ARIAStateDict) -> str:
    return scratch_edges.route_after_graph_builder(ARIAState.model_validate(state))


def route_after_impact_analyzer(state: ARIAStateDict) -> str:
    return scratch_edges.route_after_impact_analyzer(ARIAState.model_validate(state))
