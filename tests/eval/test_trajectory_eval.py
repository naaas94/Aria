"""Trajectory evaluation for the scratch orchestration engine.

Validates routing, path completeness, state mutations, error propagation,
step limits, and trace serialization against ``aria.orchestration.scratch``.

Run: pytest tests/eval/test_trajectory_eval.py -v --tb=short -m eval

Trajectory matrix (input conditions → expected behavior)
==========================================================

All paths use ``build_default_graph()`` unless noted. Supervisor routing is
implemented in ``edges.route_after_supervisor``; intent labels come from
``SupervisorAgent._classify_intent`` (``aria/agents/supervisor.py``). The
scratch graph does not branch separately on ``gap_analysis`` vs
``impact_query`` (both set ``regulation_id`` without ``raw_document``).

Canonical sequences live in ``aria.orchestration.scratch.paths`` and should
match this matrix.

+-----------------------------+------------------+------------------------------------------+
| Input (fields set)          | Classifier intent| Expected node sequence (happy path)      |
+=============================+==================+==========================================+
| ``raw_document`` only       | ingestion        | supervisor → ingestion →                 |
|                             |                  | entity_extractor → graph_builder → end   |
+-----------------------------+------------------+------------------------------------------+
| ``raw_document`` +          | ingestion        | supervisor → ingestion →                 |
| ``regulation_id``           |                  | entity_extractor → graph_builder →       |
|                             |                  | impact_analyzer → report_generator → end   |
+-----------------------------+------------------+------------------------------------------+
| ``regulation_id`` only      | impact_query     | supervisor → impact_analyzer →         |
|                             |                  | report_generator → end                 |
+-----------------------------+------------------+------------------------------------------+
| ``regulation_id`` +         | gap_analysis     | Same as impact_query (no separate edge)  |
| ``query``                   |                  |                                          |
+-----------------------------+------------------+------------------------------------------+
| ``query`` only              | free_query       | supervisor → free_query → end            |
|                             |                  | (``final_report`` from vector search stub)|
+-----------------------------+------------------+------------------------------------------+
| none / empty                | unknown          | supervisor → end                       |
+-----------------------------+------------------+------------------------------------------+

Engine semantics (``graph.py``):
    - ``MAX_STEPS`` caps **loop body** iterations (each executes one graph
      node). When the cap is hit, ``state.error`` is set to the exceeded-max
      message and the optional ``end`` node does **not** run unless
      ``current == "end"`` already.
    - On node exception or ``state.error``, edges that would advance beyond
      ``end`` are overridden so ``next_node`` becomes ``end``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from aria.agents.supervisor import SupervisorAgent
from aria.contracts.graph_entities import GraphWriteStatus
from aria.contracts.impact import AffectedAsset, CoverageStatus, ImpactReport
from aria.contracts.regulation import ExtractedEntities
from aria.orchestration.scratch.edges import (
    route_after_entity_extractor,
    route_after_free_query,
    route_after_graph_builder,
    route_after_impact_analyzer,
    route_after_ingestion,
    route_after_report_generator,
    route_after_supervisor,
)
from aria.orchestration.scratch.paths import (
    CANONICAL_SCRATCH_FREE_QUERY_PATH,
    CANONICAL_SCRATCH_IMPACT_QUERY_PATH,
    CANONICAL_SCRATCH_INGESTION_PATH_NO_REG,
    CANONICAL_SCRATCH_INGESTION_PATH_WITH_REG,
    CANONICAL_SCRATCH_UNKNOWN_PATH,
)
from aria.orchestration.scratch.graph import ExecutionResult, OrchestrationGraph, StepTrace
from aria.orchestration.scratch.graph import build_default_graph
from aria.orchestration.scratch.nodes import end_node, supervisor_node
from aria.orchestration.scratch.state import ARIAState


pytestmark = pytest.mark.eval


def _minimal_extracted_entities(doc_hash: str = "h1") -> dict[str, Any]:
    return {
        "source_document_hash": doc_hash,
        "regulations": [
            {
                "id": "reg-1",
                "title": "Test Regulation",
                "jurisdiction": "EU",
                "domain": "privacy",
                "articles": [],
            }
        ],
    }


def _minimal_impact_row() -> dict[str, Any]:
    return {
        "regulation": "Test Regulation",
        "system_id": "sys-1",
        "system_name": "Core DB",
        "team": "Platform",
        "requirement_id": "req-1",
        "requirement": "Encrypt data at rest",
        "policy_id": "pol-1",
        "policy_title": "Encryption Standard",
    }


class FakeToolPorts:
    """Async stub implementing ``ToolPorts`` for deterministic trajectories."""

    def __init__(
        self,
        *,
        extract_payload: dict[str, Any] | None = None,
        graph_write_payload: dict[str, Any] | None = None,
        impact_rows: list[dict[str, Any]] | None = None,
        report_text: str = "Final compliance report.",
        fail_extract: bool = False,
        fail_graph_write: bool = False,
        fail_query: bool = False,
        fail_generate: bool = False,
        fail_vector_search: bool = False,
        vector_hits: list[dict[str, Any]] | None = None,
    ) -> None:
        self.extract_payload = extract_payload or _minimal_extracted_entities()
        self.graph_write_payload = graph_write_payload or {
            "nodes_created": 1,
            "nodes_merged": 0,
            "edges_created": 0,
            "edges_merged": 0,
            "errors": [],
        }
        self.impact_rows = impact_rows if impact_rows is not None else [_minimal_impact_row()]
        self.report_text = report_text
        self.fail_extract = fail_extract
        self.fail_graph_write = fail_graph_write
        self.fail_query = fail_query
        self.fail_generate = fail_generate
        self.fail_vector_search = fail_vector_search
        self.vector_hits = vector_hits

    async def extract_entities(self, text: str, doc_hash: str) -> dict:
        if self.fail_extract:
            raise RuntimeError("extract_entities failed")
        return self.extract_payload

    async def write_to_graph(self, entities: dict) -> dict:
        if self.fail_graph_write:
            raise RuntimeError("write_to_graph failed")
        return self.graph_write_payload

    async def index_vectors(self, chunks: list[dict]) -> bool:
        return True

    async def query_graph(self, query_name: str, params: dict) -> list[dict]:
        if self.fail_query:
            raise RuntimeError("query_graph failed")
        return list(self.impact_rows)

    async def vector_search(self, query: str, top_k: int) -> list[dict]:
        if self.fail_vector_search:
            raise RuntimeError("vector_search failed")
        if self.vector_hits is not None:
            return list(self.vector_hits)
        return []

    async def generate_text(self, messages: list[dict]) -> str:
        if self.fail_generate:
            raise RuntimeError("generate_text failed")
        return self.report_text


# --- Supervisor intent classification (all five intents) ---


@pytest.mark.parametrize(
    ("payload", "expected_intent"),
    [
        ({"raw_document": "doc"}, "ingestion"),
        ({"regulation_id": "r1"}, "impact_query"),
        ({"regulation_id": "r1", "query": "gaps?"}, "gap_analysis"),
        ({"query": "what applies?"}, "free_query"),
        ({}, "unknown"),
        ({"extra": 1}, "unknown"),
    ],
)
@pytest.mark.asyncio
async def test_supervisor_classifies_all_intent_types(payload: dict, expected_intent: str) -> None:
    agent = SupervisorAgent()
    out = await agent.process(payload)
    assert out["intent"] == expected_intent


# --- Routing correctness (edge functions mirror state flags) ---


@pytest.mark.parametrize(
    ("state_kwargs", "expected_next"),
    [
        ({}, "end"),
        ({"raw_document": "x"}, "ingestion"),
        ({"regulation_id": "r"}, "impact_analyzer"),
        ({"query": "q"}, "free_query"),
        ({"regulation_id": "r", "query": "q"}, "impact_analyzer"),
        ({"error": "e"}, "end"),
    ],
)
def test_route_after_supervisor(state_kwargs: dict, expected_next: str) -> None:
    state = ARIAState(**state_kwargs)
    assert route_after_supervisor(state) == expected_next


def test_route_after_supervisor_ingestion_wins_over_regulation_id() -> None:
    """Document + ID is still an ingestion request (``is_ingestion_request`` first)."""
    state = ARIAState(raw_document="body", regulation_id="r1")
    assert route_after_supervisor(state) == "ingestion"


def test_route_after_ingestion_to_extractor_or_end() -> None:
    err = ARIAState(raw_document="d", error="failed")
    assert route_after_ingestion(err) == "end"
    ok = ARIAState(raw_document="d")
    assert route_after_ingestion(ok) == "entity_extractor"


def test_route_after_entity_extractor_branches() -> None:
    err = ARIAState(raw_document="d", error="failed")
    assert route_after_entity_extractor(err) == "end"
    empty = ARIAState(raw_document="d")
    assert route_after_entity_extractor(empty) == "end"
    filled = ARIAState(raw_document="d")
    filled.extracted_entities = ExtractedEntities.model_validate(_minimal_extracted_entities())
    assert route_after_entity_extractor(filled) == "graph_builder"


def test_route_after_free_query_always_end() -> None:
    assert route_after_free_query(ARIAState()) == "end"


@pytest.mark.parametrize(
    ("has_reg_id", "expected"),
    [
        (False, "end"),
        (True, "impact_analyzer"),
    ],
)
def test_route_after_graph_builder_regulation_id_branch(has_reg_id: bool, expected: str) -> None:
    state = ARIAState()
    state.extracted_entities = ExtractedEntities.model_validate(_minimal_extracted_entities())
    state.graph_write_status = GraphWriteStatus()
    if has_reg_id:
        state.regulation_id = "r1"
    assert route_after_graph_builder(state) == expected


def test_route_after_impact_analyzer() -> None:
    empty = ARIAState(regulation_id="r1")
    assert route_after_impact_analyzer(empty) == "end"
    filled = ARIAState(regulation_id="r1")
    filled.impact_report = ImpactReport(
        regulation_id="r1",
        regulation_title="T",
        total_requirements=1,
        affected_systems=[
            AffectedAsset(
                system_id="s",
                system_name="n",
                owner_team="o",
                requirement_id="rq",
                requirement_text="t",
                coverage_status=CoverageStatus.COVERED,
            )
        ],
        coverage_summary={CoverageStatus.COVERED: 1},
    )
    assert route_after_impact_analyzer(filled) == "report_generator"


def test_route_after_report_generator_always_end() -> None:
    state = ARIAState()
    assert route_after_report_generator(state) == "end"


# --- Path completeness (async execute) ---


@pytest.mark.asyncio
async def test_path_unknown_supervisor_to_end() -> None:
    graph = build_default_graph()
    tools = FakeToolPorts()
    state = ARIAState()
    result = await graph.execute(state, tools)
    assert result.node_path == ["supervisor", "end"]
    assert result.success
    assert result.final_state.error is None


@pytest.mark.asyncio
async def test_path_free_query_uses_vector_search_branch() -> None:
    graph = build_default_graph()
    tools = FakeToolPorts(
        vector_hits=[{"text": "Chunk about GDPR retention.", "score": 0.9}]
    )
    state = ARIAState(query="ad-hoc question")
    result = await graph.execute(state, tools)
    assert result.node_path == ["supervisor", "free_query", "end"]
    assert result.success
    assert result.final_state.final_report is not None
    assert "GDPR" in result.final_state.final_report


@pytest.mark.asyncio
async def test_path_impact_query_full() -> None:
    graph = build_default_graph()
    tools = FakeToolPorts()
    state = ARIAState(regulation_id="reg-1")
    result = await graph.execute(state, tools)
    assert result.node_path == ["supervisor", "impact_analyzer", "report_generator", "end"]
    assert result.success
    assert result.final_state.impact_report is not None
    assert result.final_state.final_report == tools.report_text


@pytest.mark.asyncio
async def test_path_gap_analysis_same_as_impact_query() -> None:
    graph = build_default_graph()
    tools = FakeToolPorts()
    state = ARIAState(regulation_id="reg-1", query="show gaps")
    result = await graph.execute(state, tools)
    assert result.node_path == ["supervisor", "impact_analyzer", "report_generator", "end"]
    agent = SupervisorAgent()
    assert (await agent.process({"regulation_id": "reg-1", "query": "show gaps"}))[
        "intent"
    ] == "gap_analysis"


@pytest.mark.asyncio
async def test_path_ingestion_no_regulation_id_ends_after_graph_builder() -> None:
    graph = build_default_graph()
    tools = FakeToolPorts()
    state = ARIAState(raw_document="policy text", document_hash="abc")
    result = await graph.execute(state, tools)
    assert result.node_path == ["supervisor", "ingestion", "entity_extractor", "graph_builder", "end"]
    assert result.success
    assert isinstance(result.final_state.extracted_entities, ExtractedEntities)
    assert result.final_state.graph_write_status is not None


@pytest.mark.asyncio
async def test_path_ingestion_with_regulation_id_runs_full_compliance_chain() -> None:
    graph = build_default_graph()
    tools = FakeToolPorts()
    state = ARIAState(
        raw_document="policy text",
        document_hash="abc",
        regulation_id="reg-1",
    )
    result = await graph.execute(state, tools)
    assert result.node_path == [
        "supervisor",
        "ingestion",
        "entity_extractor",
        "graph_builder",
        "impact_analyzer",
        "report_generator",
        "end",
    ]
    assert result.success


@pytest.mark.asyncio
async def test_default_execute_paths_match_canonical_constants() -> None:
    """``paths`` module stays aligned with ``build_default_graph``."""
    graph = build_default_graph()
    tools = FakeToolPorts()
    tools_empty_vec = FakeToolPorts()

    r_unknown = await graph.execute(ARIAState(), tools)
    assert r_unknown.node_path == CANONICAL_SCRATCH_UNKNOWN_PATH

    r_free = await graph.execute(ARIAState(query="q"), tools_empty_vec)
    assert r_free.node_path == CANONICAL_SCRATCH_FREE_QUERY_PATH

    r_impact = await graph.execute(ARIAState(regulation_id="r1"), tools)
    assert r_impact.node_path == CANONICAL_SCRATCH_IMPACT_QUERY_PATH

    r_ingest = await graph.execute(
        ARIAState(raw_document="x", document_hash="h"),
        tools,
    )
    assert r_ingest.node_path == CANONICAL_SCRATCH_INGESTION_PATH_NO_REG

    r_ingest_reg = await graph.execute(
        ARIAState(raw_document="x", document_hash="h", regulation_id="r1"),
        tools,
    )
    assert r_ingest_reg.node_path == CANONICAL_SCRATCH_INGESTION_PATH_WITH_REG


# --- State mutations ---


@pytest.mark.asyncio
async def test_ingestion_populates_extracted_entities() -> None:
    graph = build_default_graph()
    tools = FakeToolPorts()
    state = ARIAState(raw_document="x", document_hash="dh")
    result = await graph.execute(state, tools)
    ee = result.final_state.extracted_entities
    assert ee is not None
    assert ee.source_document_hash == tools.extract_payload["source_document_hash"]


@pytest.mark.asyncio
async def test_impact_analyzer_populates_impact_report() -> None:
    graph = build_default_graph()
    tools = FakeToolPorts()
    state = ARIAState(regulation_id="reg-1")
    result = await graph.execute(state, tools)
    ir = result.final_state.impact_report
    assert ir is not None
    assert ir.regulation_id == "reg-1"
    assert ir.total_requirements == len(tools.impact_rows)


@pytest.mark.asyncio
async def test_report_generator_populates_final_report() -> None:
    graph = build_default_graph()
    tools = FakeToolPorts()
    state = ARIAState(regulation_id="reg-1")
    result = await graph.execute(state, tools)
    assert result.final_state.final_report == "Final compliance report."


# --- Error propagation ---


@pytest.mark.asyncio
async def test_ingestion_error_routes_to_end_with_state_error() -> None:
    graph = build_default_graph()
    tools = FakeToolPorts()
    # ``is_ingestion_request`` is True (not None), but body treats "" as missing.
    state = ARIAState(raw_document="")
    result = await graph.execute(state, tools)
    assert result.node_path == ["supervisor", "ingestion", "end"]
    assert result.final_state.error is not None


@pytest.mark.asyncio
async def test_node_exception_sets_error_and_ends() -> None:
    graph = build_default_graph()
    tools = FakeToolPorts(fail_extract=True)
    state = ARIAState(raw_document="x", document_hash="h")
    result = await graph.execute(state, tools)
    assert not result.success
    assert "Entity extraction failed" in (result.final_state.error or "")
    assert result.node_path[-1] == "end"


@pytest.mark.asyncio
async def test_graph_write_failure_sets_error() -> None:
    graph = build_default_graph()
    tools = FakeToolPorts(
        graph_write_payload={
            "nodes_created": 0,
            "errors": ["merge conflict"],
        }
    )
    state = ARIAState(raw_document="x", document_hash="h")
    result = await graph.execute(state, tools)
    assert not result.success
    assert result.final_state.error is not None


# --- MAX_STEPS ---


@pytest.mark.asyncio
async def test_max_steps_stops_infinite_loop_and_sets_error() -> None:
    graph = OrchestrationGraph(entry_point="loop", max_steps=4)
    graph.add_node("loop", supervisor_node)
    graph.add_edge("loop", lambda _s: "loop")
    graph.add_node("end", end_node)

    tools = FakeToolPorts()
    state = ARIAState()
    result = await graph.execute(state, tools)
    assert len([t for t in result.traces if t.node_name == "loop"]) == 4
    assert result.final_state.error is not None
    assert "max steps" in result.final_state.error.lower()
    assert result.node_path[-1] == "loop"


@pytest.mark.asyncio
async def test_max_steps_20_allows_twentieth_step_before_bail() -> None:
    """With max_steps=20, the body runs while step_count < 20, i.e. 20 iterations."""
    graph = OrchestrationGraph(entry_point="loop", max_steps=20)
    graph.add_node("loop", supervisor_node)
    graph.add_edge("loop", lambda _s: "loop")

    tools = FakeToolPorts()
    state = ARIAState()
    result = await graph.execute(state, tools)
    loop_traces = [t for t in result.traces if t.node_name == "loop"]
    assert len(loop_traces) == 20
    assert "max steps" in (result.final_state.error or "").lower()
    # There is no 21st loop iteration: while condition fails when step_count == 20.


# --- Trace fidelity ---


def test_execution_result_to_trace_dict_matches_internal_traces() -> None:
    state = ARIAState(error="boom")
    traces = [
        StepTrace(node_name="supervisor", duration_ms=1.0, next_node="end", error="boom"),
        StepTrace(node_name="end", duration_ms=0.0, next_node="done", error=None),
    ]
    result = ExecutionResult(final_state=state, traces=traces)
    d = result.to_trace_dict()
    assert d["success"] is False
    assert d["total_duration_ms"] == 1.0
    assert d["node_path"] == ["supervisor", "end"]
    assert len(d["steps"]) == 2
    assert d["steps"][0]["node"] == "supervisor"
    assert d["steps"][0]["error"] == "boom"
    assert d["steps"][1]["next_node"] == "done"


@pytest.mark.asyncio
async def test_to_trace_dict_matches_live_execute() -> None:
    graph = build_default_graph()
    tools = FakeToolPorts()
    state = ARIAState(regulation_id="r1")
    result = await graph.execute(state, tools)
    d = result.to_trace_dict()
    assert d["node_path"] == result.node_path
    assert d["success"] == result.success
    assert len(d["steps"]) == len(result.traces)


# --- Concurrent runs (isolated state per execution) ---


@pytest.mark.asyncio
async def test_concurrent_executions_do_not_cross_contaminate_state() -> None:
    graph = build_default_graph()
    tools = FakeToolPorts()

    async def run(reg_id: str) -> ARIAState:
        res = await graph.execute(ARIAState(regulation_id=reg_id), tools)
        return res.final_state

    s1, s2 = await asyncio.gather(run("reg-a"), run("reg-b"))
    assert s1.regulation_id == "reg-a"
    assert s2.regulation_id == "reg-b"
    assert s1.impact_report is not None and s2.impact_report is not None
    assert s1.impact_report.regulation_id != s2.impact_report.regulation_id
