"""Graph assembly and execution engine for the scratch orchestration.

Implements the core loop: start at entry_point, execute node, evaluate
edge condition, advance to next node, repeat until "end" or error.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from aria.orchestration.scratch.edges import EDGE_MAP, EdgeFunction
from aria.orchestration.scratch.nodes import ToolPorts
from aria.orchestration.scratch.state import ARIAState

logger = logging.getLogger(__name__)

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


class OrchestrationGraph:
    """Stateful graph that executes nodes and follows edges until termination."""

    def __init__(self, entry_point: str = "supervisor") -> None:
        self._entry_point = entry_point
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
        error, or after MAX_STEPS to prevent infinite loops.
        """
        result = ExecutionResult(final_state=state)
        current = self._entry_point
        step_count = 0

        while current != "end" and step_count < MAX_STEPS:
            if current not in self._nodes:
                state.error = f"Unknown node: {current}"
                break

            start = time.monotonic()
            try:
                state = await self._nodes[current](state, tools)
            except Exception as exc:
                state.error = f"Node {current} raised: {exc}"
                logger.exception("Node %s failed", current)

            elapsed_ms = (time.monotonic() - start) * 1000

            edge_fn = self._edges.get(current)
            next_node = edge_fn(state) if edge_fn else "end"

            result.traces.append(
                StepTrace(
                    node_name=current,
                    duration_ms=elapsed_ms,
                    next_node=next_node,
                    error=state.error,
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

        if step_count >= MAX_STEPS:
            state.error = f"Orchestration exceeded max steps ({MAX_STEPS})"
            logger.error(state.error)

        result.final_state = state
        return result


def build_default_graph() -> OrchestrationGraph:
    """Construct the standard ARIA orchestration graph with all nodes wired."""
    from aria.orchestration.scratch.nodes import (
        end_node,
        graph_builder_node,
        impact_analyzer_node,
        ingestion_node,
        report_generator_node,
        supervisor_node,
    )

    graph = OrchestrationGraph(entry_point="supervisor")
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("ingestion", ingestion_node)
    graph.add_node("graph_builder", graph_builder_node)
    graph.add_node("impact_analyzer", impact_analyzer_node)
    graph.add_node("report_generator", report_generator_node)
    graph.add_node("end", end_node)

    return graph
