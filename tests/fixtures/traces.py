"""AgentTrace fixtures for trace evaluation and orchestration offline tests."""

from __future__ import annotations

from tests.eval.agent_trace_analysis import AgentTrace, TraceStep

# ---------------------------------------------------------------------------
# Golden / happy paths (≥3)
# ---------------------------------------------------------------------------

TRACE_GOLDEN_INGESTION_FLOW = AgentTrace(
    trace_id="golden-ingestion-001",
    steps=[
        TraceStep(
            node_name="supervisor",
            input_state={"raw_document": "..."},
            output_state={"intent": "ingestion"},
            tool_calls=["classify_intent"],
            duration_ms=12.0,
        ),
        TraceStep(node_name="ingestion", input_state={}, output_state={}, duration_ms=5.0),
        TraceStep(node_name="entity_extractor", input_state={}, output_state={}, duration_ms=120.0),
        TraceStep(node_name="graph_builder", input_state={}, output_state={}, duration_ms=45.0),
        TraceStep(node_name="end", input_state={}, output_state={}, duration_ms=1.0),
    ],
)

TRACE_GOLDEN_IMPACT_QUERY_FLOW = AgentTrace(
    trace_id="golden-impact-001",
    steps=[
        TraceStep(
            node_name="supervisor",
            input_state={"regulation_id": "reg-gdpr"},
            output_state={"intent": "impact_query"},
            duration_ms=8.0,
        ),
        TraceStep(
            node_name="impact_analyzer",
            input_state={},
            output_state={"impact_report": {}},
            tool_calls=["impact_by_regulation"],
            duration_ms=200.0,
        ),
        TraceStep(node_name="report_generator", input_state={}, output_state={"final_report": "..."}, duration_ms=90.0),
        TraceStep(node_name="end", input_state={}, output_state={}, duration_ms=1.0),
    ],
)

TRACE_GOLDEN_GAP_ANALYSIS_FLOW = AgentTrace(
    trace_id="golden-gap-001",
    steps=[
        TraceStep(
            node_name="supervisor",
            input_state={"regulation_id": "reg-eu-ai-act", "query": "List gaps"},
            output_state={"intent": "gap_analysis"},
            duration_ms=10.0,
        ),
        TraceStep(
            node_name="impact_analyzer",
            input_state={},
            output_state={},
            tool_calls=["impact_by_regulation", "uncovered_requirements"],
            duration_ms=150.0,
        ),
        TraceStep(node_name="report_generator", input_state={}, output_state={}, duration_ms=80.0),
        TraceStep(node_name="end", input_state={}, output_state={}, duration_ms=1.0),
    ],
)

# ---------------------------------------------------------------------------
# Error paths (≥1 explicit)
# ---------------------------------------------------------------------------

TRACE_ERROR_LLM_FAILURE = AgentTrace(
    trace_id="error-llm-001",
    steps=[
        TraceStep(
            node_name="supervisor",
            input_state={},
            output_state={},
            error="Model returned invalid JSON",
            duration_ms=30000.0,
        ),
    ],
)

TRACE_ERROR_ENTITY_EXTRACTION = AgentTrace(
    trace_id="error-extract-001",
    steps=[
        TraceStep(node_name="supervisor", input_state={}, output_state={}, duration_ms=5.0),
        TraceStep(node_name="ingestion", input_state={}, output_state={}, duration_ms=4.0),
        TraceStep(
            node_name="entity_extractor",
            input_state={},
            output_state={},
            error="Schema validation failed for ExtractedEntities",
            duration_ms=200.0,
        ),
    ],
)

# ---------------------------------------------------------------------------
# Looping path
# ---------------------------------------------------------------------------

TRACE_LOOP_ENTITY_EXTRACTOR = AgentTrace(
    trace_id="loop-extractor-001",
    steps=[
        TraceStep(node_name="supervisor", input_state={}, output_state={}, duration_ms=2.0),
        *[TraceStep(node_name="entity_extractor", input_state={}, output_state={}, duration_ms=10.0) for _ in range(5)],
    ],
)

# ---------------------------------------------------------------------------
# Timeout path (very large duration_ms on a step)
# ---------------------------------------------------------------------------

TRACE_TIMEOUT_GRAPH_BUILDER = AgentTrace(
    trace_id="timeout-graph-001",
    steps=[
        TraceStep(node_name="supervisor", input_state={}, output_state={}, duration_ms=5.0),
        TraceStep(node_name="ingestion", input_state={}, output_state={}, duration_ms=5.0),
        TraceStep(node_name="entity_extractor", input_state={}, output_state={}, duration_ms=100.0),
        TraceStep(
            node_name="graph_builder",
            input_state={},
            output_state={},
            duration_ms=600000.0,
            error="Client timeout waiting for Neo4j MERGE batch",
        ),
    ],
)

# ---------------------------------------------------------------------------
# Adversarial paths (≥5 scenarios total across error/loop/timeout/adv — extra adv below)
# ---------------------------------------------------------------------------

TRACE_ADV_NODE_VISITED_100_TIMES = AgentTrace(
    trace_id="adv-hot-loop-001",
    steps=[
        TraceStep(node_name="supervisor", input_state={}, output_state={}, duration_ms=1.0),
        *[TraceStep(node_name="entity_extractor", input_state={}, output_state={}, duration_ms=0.5) for _ in range(100)],
    ],
)

TRACE_ADV_UNKNOWN_NODES = AgentTrace(
    trace_id="adv-unknown-nodes-001",
    steps=[
        TraceStep(node_name="supervisor", input_state={}, output_state={}, duration_ms=3.0),
        TraceStep(node_name="phantom_router_Ω", input_state={}, output_state={}, duration_ms=1.0),
        TraceStep(node_name="legacy_node_deprecated", input_state={}, output_state={}, duration_ms=2.0),
        TraceStep(node_name="end", input_state={}, output_state={}, duration_ms=1.0),
    ],
)

TRACE_ADV_SUPERVISOR_SPAM = AgentTrace(
    trace_id="adv-supervisor-spam-001",
    steps=[TraceStep(node_name="supervisor", input_state={}, output_state={}, duration_ms=1.0) for _ in range(25)],
)

TRACE_ADV_WRONG_ORDER = AgentTrace(
    trace_id="adv-wrong-order-001",
    steps=[
        TraceStep(node_name="report_generator", input_state={}, output_state={}, duration_ms=5.0),
        TraceStep(node_name="supervisor", input_state={}, output_state={}, duration_ms=5.0),
        TraceStep(node_name="end", input_state={}, output_state={}, duration_ms=1.0),
    ],
)

TRACE_ADV_TOOL_EXPLOSION = AgentTrace(
    trace_id="adv-tool-explosion-001",
    steps=[
        TraceStep(
            node_name="impact_analyzer",
            input_state={},
            output_state={},
            tool_calls=[f"impact_by_regulation_chunk_{i}" for i in range(40)],
            duration_ms=500.0,
        ),
    ],
)
