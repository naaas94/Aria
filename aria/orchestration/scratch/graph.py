"""Graph assembly and execution engine for the scratch orchestration.

Implements the core loop: start at entry_point, execute node, evaluate
edge condition, advance to next node, repeat until "end" or error.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import structlog

from aria.observability.metrics import (
    AGENT_EXECUTION_COUNTER,
    AGENT_EXECUTION_DURATION,
    TELEMETRY_WRITE_ERRORS_COUNTER,
)
from aria.observability.telemetry_store import get_telemetry_store
from aria.orchestration.scratch.edges import EDGE_MAP, EdgeFunction
from aria.orchestration.scratch.nodes import ToolPorts
from aria.orchestration.scratch.state import ARIAState

logger = logging.getLogger(__name__)

# Synthetic ``agent_name`` for ``agent_executions`` / Prometheus (scratch graph is not BaseAgent).
ORCHESTRATION_SCRATCH_AGENT_NAME = "orchestration.scratch"

NodeFunction = Callable[[ARIAState, ToolPorts], Awaitable[ARIAState]]

MAX_STEPS = 20


@dataclass
class StepTrace:
    node_name: str
    duration_ms: float
    next_node: str
    error: str | None = None


@dataclass
class ExecutionResult:
    final_state: ARIAState
    traces: list[StepTrace] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.final_state.has_error

    @property
    def total_duration_ms(self) -> float:
        return sum(t.duration_ms for t in self.traces)

    @property
    def node_path(self) -> list[str]:
        return [t.node_name for t in self.traces]

    def to_trace_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "total_duration_ms": self.total_duration_ms,
            "node_path": self.node_path,
            "steps": [
                {
                    "node": t.node_name,
                    "duration_ms": t.duration_ms,
                    "next_node": t.next_node,
                    "error": t.error,
                }
                for t in self.traces
            ],
        }


def _record_scratch_orchestration_telemetry(result: ExecutionResult) -> None:
    """One row per graph run: same store and labels as ``BaseAgent.run()`` (pragmatic aggregate)."""
    status = "success" if result.success else "error"
    err = result.final_state.error
    duration_ms = result.total_duration_ms
    request_id = structlog.contextvars.get_contextvars().get("request_id")

    try:
        get_telemetry_store().record_agent_execution(
            request_id=request_id,
            agent_name=ORCHESTRATION_SCRATCH_AGENT_NAME,
            status=status,
            error=err,
            duration_ms=duration_ms,
        )
    except Exception as exc:
        TELEMETRY_WRITE_ERRORS_COUNTER.labels(source="orchestration").inc()
        logger.warning(
            "record_agent_execution failed for scratch orchestration: %s",
            type(exc).__name__,
        )

    AGENT_EXECUTION_COUNTER.labels(
        agent_name=ORCHESTRATION_SCRATCH_AGENT_NAME,
        status=status,
    ).inc()
    AGENT_EXECUTION_DURATION.labels(
        agent_name=ORCHESTRATION_SCRATCH_AGENT_NAME,
    ).observe(duration_ms / 1000.0)


class OrchestrationGraph:
    """Stateful graph that executes nodes and follows edges until termination."""

    def __init__(self, entry_point: str = "supervisor", *, max_steps: int | None = None) -> None:
        self._entry_point = entry_point
        self._max_steps = max_steps if max_steps is not None else MAX_STEPS
        self._nodes: dict[str, NodeFunction] = {}
        self._edges: dict[str, EdgeFunction] = dict(EDGE_MAP)

    def add_node(self, name: str, fn: NodeFunction) -> None:
        self._nodes[name] = fn

    def add_edge(self, from_node: str, edge_fn: EdgeFunction) -> None:
        self._edges[from_node] = edge_fn

    async def execute(self, state: ARIAState, tools: ToolPorts) -> ExecutionResult:
        """Run the orchestration graph to completion.

        The loop executes the current node, evaluates the outgoing edge
        to determine the next node, and advances. Terminates on "end",
        error, or after ``self._max_steps`` iterations (default
        ``MAX_STEPS``) to prevent infinite loops.

        If the run completes with ``current == "end"`` after the last
        transition (including when the final loop iteration advanced to
        ``end``), the max-step guard does **not** set ``state.error``,
        even when ``step_count`` equals the limit.
        """
        result = ExecutionResult(final_state=state)
        current = self._entry_point
        step_count = 0

        while current != "end" and step_count < self._max_steps:
            if current not in self._nodes:
                state.error = f"Unknown node: {current}"
                break

            start = time.monotonic()
            prev_state = state
            error_before = prev_state.error
            try:
                out = await self._nodes[current](state, tools)
            except Exception as exc:
                state.error = f"Node {current} raised: {exc}"
                logger.exception("Node %s failed", current)
            else:
                if not isinstance(out, ARIAState):
                    logger.error(
                        "Node %s returned invalid state (expected ARIAState, got %s)",
                        current,
                        type(out).__name__,
                    )
                    state = prev_state
                    state.error = (
                        f"Node {current} returned invalid state (expected ARIAState)"
                    )
                else:
                    state = out

            elapsed_ms = (time.monotonic() - start) * 1000

            edge_fn = self._edges.get(current)
            next_node = edge_fn(state) if edge_fn else "end"

            trace_error = (
                state.error if (state.error and not error_before) else None
            )
            result.traces.append(
                StepTrace(
                    node_name=current,
                    duration_ms=elapsed_ms,
                    next_node=next_node,
                    error=trace_error,
                )
            )

            if state.has_error and next_node != "end":
                next_node = "end"

            current = next_node
            step_count += 1

        if current == "end" and "end" in self._nodes:
            state = await self._nodes["end"](state, tools)
            result.traces.append(
                StepTrace(node_name="end", duration_ms=0, next_node="done")
            )

        if step_count >= self._max_steps and current != "end":
            state.error = f"Orchestration exceeded max steps ({self._max_steps})"
            logger.error(state.error)

        result.final_state = state
        _record_scratch_orchestration_telemetry(result)
        return result


def build_default_graph() -> OrchestrationGraph:
    """Construct the standard ARIA orchestration graph with all nodes wired."""
    from aria.orchestration.scratch.nodes import (
        end_node,
        entity_extractor_node,
        free_query_node,
        graph_builder_node,
        impact_analyzer_node,
        ingestion_node,
        report_generator_node,
        supervisor_node,
    )

    graph = OrchestrationGraph(entry_point="supervisor")
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("ingestion", ingestion_node)
    graph.add_node("entity_extractor", entity_extractor_node)
    graph.add_node("free_query", free_query_node)
    graph.add_node("graph_builder", graph_builder_node)
    graph.add_node("impact_analyzer", impact_analyzer_node)
    graph.add_node("report_generator", report_generator_node)
    graph.add_node("end", end_node)

    return graph
