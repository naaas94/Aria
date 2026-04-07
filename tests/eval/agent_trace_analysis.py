"""Evaluates agent decision traces for correctness and efficiency.

Analyzes structured traces produced by the orchestration engine to
validate that agents make correct routing decisions, tool calls,
and state transitions.

Run: pytest tests/eval/agent_trace_analysis.py -v --tb=short -m eval
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass
class TraceStep:
    """A single step in an agent execution trace."""

    node_name: str
    input_state: dict[str, Any]
    output_state: dict[str, Any]
    tool_calls: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    error: str | None = None


@dataclass
class AgentTrace:
    """Full execution trace for an orchestration run."""

    trace_id: str
    steps: list[TraceStep] = field(default_factory=list)

    @property
    def node_sequence(self) -> list[str]:
        return [s.node_name for s in self.steps]

    @property
    def total_duration_ms(self) -> float:
        return sum(s.duration_ms for s in self.steps)

    @property
    def has_errors(self) -> bool:
        return any(s.error is not None for s in self.steps)

    @property
    def tool_call_count(self) -> int:
        return sum(len(s.tool_calls) for s in self.steps)


@dataclass
class TraceEvaluation:
    """Evaluation result for a single trace."""

    trace_id: str
    correct_routing: bool = True
    correct_tool_usage: bool = True
    efficient_path: bool = True
    completed_successfully: bool = True
    issues: list[str] = field(default_factory=list)


from aria.orchestration.scratch.paths import (
    CANONICAL_SCRATCH_FREE_QUERY_PATH,
    CANONICAL_SCRATCH_IMPACT_QUERY_PATH,
    CANONICAL_SCRATCH_INGESTION_PATH_NO_REG,
)

EXPECTED_INGESTION_FLOW = CANONICAL_SCRATCH_INGESTION_PATH_NO_REG
EXPECTED_QUERY_FLOW = CANONICAL_SCRATCH_IMPACT_QUERY_PATH
EXPECTED_FREE_QUERY_FLOW = CANONICAL_SCRATCH_FREE_QUERY_PATH


def evaluate_trace(
    trace: AgentTrace,
    expected_flow: list[str] | None = None,
) -> TraceEvaluation:
    """Evaluate a trace against expected behavior."""
    evaluation = TraceEvaluation(trace_id=trace.trace_id)

    if trace.has_errors:
        evaluation.completed_successfully = False
        for step in trace.steps:
            if step.error:
                evaluation.issues.append(f"Error at {step.node_name}: {step.error}")

    if expected_flow:
        actual = trace.node_sequence
        if actual != expected_flow:
            evaluation.correct_routing = False
            evaluation.issues.append(
                f"Expected flow {expected_flow}, got {actual}"
            )

    if len(trace.steps) > 10:
        evaluation.efficient_path = False
        evaluation.issues.append(f"Trace has {len(trace.steps)} steps (expected <10)")

    seen_nodes: dict[str, int] = {}
    for step in trace.steps:
        seen_nodes[step.node_name] = seen_nodes.get(step.node_name, 0) + 1
    for node, count in seen_nodes.items():
        if count > 3 and node != "supervisor":
            evaluation.efficient_path = False
            evaluation.issues.append(f"Node {node} visited {count} times (possible loop)")

    return evaluation


@pytest.mark.eval
class TestTraceEvaluation:
    def test_correct_ingestion_trace(self):
        trace = AgentTrace(
            trace_id="t1",
            steps=[
                TraceStep(node_name="supervisor", input_state={}, output_state={"raw_document": "..."}),
                TraceStep(node_name="ingestion", input_state={}, output_state={}),
                TraceStep(node_name="entity_extractor", input_state={}, output_state={}),
                TraceStep(node_name="graph_builder", input_state={}, output_state={}),
                TraceStep(node_name="end", input_state={}, output_state={}),
            ],
        )
        result = evaluate_trace(trace, EXPECTED_INGESTION_FLOW)
        assert result.correct_routing
        assert result.completed_successfully
        assert result.efficient_path

    def test_error_trace_detected(self):
        trace = AgentTrace(
            trace_id="t2",
            steps=[
                TraceStep(node_name="supervisor", input_state={}, output_state={}, error="LLM timeout"),
            ],
        )
        result = evaluate_trace(trace)
        assert not result.completed_successfully

    def test_loop_detection(self):
        steps = [
            TraceStep(node_name="entity_extractor", input_state={}, output_state={})
            for _ in range(5)
        ]
        trace = AgentTrace(trace_id="t3", steps=steps)
        result = evaluate_trace(trace)
        assert not result.efficient_path

    def test_wrong_routing_detected(self):
        trace = AgentTrace(
            trace_id="t4",
            steps=[
                TraceStep(node_name="supervisor", input_state={}, output_state={}),
                TraceStep(node_name="report_generator", input_state={}, output_state={}),
                TraceStep(node_name="end", input_state={}, output_state={}),
            ],
        )
        result = evaluate_trace(trace, EXPECTED_INGESTION_FLOW)
        assert not result.correct_routing
