"""LangGraph StateGraph assembly — reference implementation.

Builds the identical orchestration graph as the scratch engine using
LangGraph's StateGraph API. This is the comparison artifact: same
logic, framework-expressed.

Requires: pip install "aria[langgraph]"
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_langgraph() -> Any:
    """Construct the ARIA orchestration graph using LangGraph.

    Returns the compiled LangGraph StateGraph. Raises ImportError
    if langgraph is not installed.
    """
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        raise ImportError(
            "LangGraph is not installed. Install with: pip install 'aria[langgraph]'"
        )

    from aria.orchestration.langgraph_reference.nodes import (
        graph_builder_node,
        impact_analyzer_node,
        ingestion_node,
        report_generator_node,
        route_after_graph_builder,
        route_after_impact_analyzer,
        route_after_ingestion,
        route_after_supervisor,
        supervisor_node,
    )
    from aria.orchestration.langgraph_reference.state import ARIAStateDict

    graph = StateGraph(ARIAStateDict)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("ingestion", ingestion_node)
    graph.add_node("graph_builder", graph_builder_node)
    graph.add_node("impact_analyzer", impact_analyzer_node)
    graph.add_node("report_generator", report_generator_node)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "ingestion": "ingestion",
            "impact_analyzer": "impact_analyzer",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "ingestion",
        route_after_ingestion,
        {
            "graph_builder": "graph_builder",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "graph_builder",
        route_after_graph_builder,
        {
            "impact_analyzer": "impact_analyzer",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "impact_analyzer",
        route_after_impact_analyzer,
        {
            "report_generator": "report_generator",
            "end": END,
        },
    )
    graph.add_edge("report_generator", END)

    compiled = graph.compile()
    logger.info("LangGraph orchestration graph compiled successfully")
    return compiled
