"""Prometheus metrics for ARIA.

Defines counters and histograms for ingestion, retrieval, agent
execution, and tool calls. Metrics are registered on import and
exposed via the /metrics endpoint.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram, Info

ARIA_INFO = Info("aria", "ARIA system metadata")
ARIA_INFO.info({"version": "0.1.0", "component": "aria-api"})

HTTP_REQUEST_COUNTER = Counter(
    "aria_http_requests_total",
    "Total HTTP API requests",
    ["method", "status_code"],
)

INGESTION_COUNTER = Counter(
    "aria_ingestion_total",
    "Total document ingestion attempts",
    ["status"],
)

INGESTION_DURATION = Histogram(
    "aria_ingestion_duration_seconds",
    "Duration of document ingestion",
    ["format"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

RETRIEVAL_COUNTER = Counter(
    "aria_retrieval_total",
    "Total retrieval queries",
    ["strategy"],
)

RETRIEVAL_DURATION = Histogram(
    "aria_retrieval_duration_seconds",
    "Duration of retrieval queries",
    ["strategy"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

AGENT_EXECUTION_COUNTER = Counter(
    "aria_agent_execution_total",
    "Total agent executions",
    ["agent_name", "status"],
)

AGENT_EXECUTION_DURATION = Histogram(
    "aria_agent_execution_duration_seconds",
    "Duration of agent executions",
    ["agent_name"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

MCP_TOOL_CALL_COUNTER = Counter(
    "aria_mcp_tool_call_total",
    "Total MCP tool invocations",
    ["tool_name", "status"],
)

MCP_TOOL_CALL_DURATION = Histogram(
    "aria_mcp_tool_call_duration_seconds",
    "Duration of MCP tool invocations",
    ["tool_name"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)

GRAPH_QUERY_COUNTER = Counter(
    "aria_graph_query_total",
    "Total graph queries executed",
    ["query_name"],
)

LLM_CALL_COUNTER = Counter(
    "aria_llm_call_total",
    "Total LLM completions",
    ["model", "status"],
)

LLM_CALL_DURATION = Histogram(
    "aria_llm_call_duration_seconds",
    "Duration of LLM completion calls",
    ["model"],
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)
