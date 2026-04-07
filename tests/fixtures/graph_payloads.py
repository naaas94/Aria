"""Pre-built GraphWritePayload values for graph builder tests (no Neo4j required)."""

from __future__ import annotations

from aria.contracts.graph_entities import EdgeType, GraphEdge, GraphNode, GraphWritePayload, NodeLabel
from aria.graph.builder import entities_to_write_payload

from tests.fixtures.entities import HAPPY_FULL_GDPR_AND_AI_ACT, HAPPY_MINIMAL_SINGLE_CHAIN

# ---------------------------------------------------------------------------
# Happy path (≥3)
# ---------------------------------------------------------------------------

HAPPY_FROM_SEED_ENTITIES: GraphWritePayload = entities_to_write_payload(HAPPY_FULL_GDPR_AND_AI_ACT)

HAPPY_FROM_MINIMAL_ENTITIES: GraphWritePayload = entities_to_write_payload(HAPPY_MINIMAL_SINGLE_CHAIN)

HAPPY_WITH_IMPACT_CHAIN = GraphWritePayload(
    nodes=[
        GraphNode(
            label=NodeLabel.JURISDICTION,
            properties={"id": "eu", "name": "European Union", "region": "EU"},
        ),
        GraphNode(
            label=NodeLabel.TEAM,
            properties={"id": "team-sec", "name": "Security", "function": "SecOps", "contact": "sec@example.com"},
        ),
        GraphNode(
            label=NodeLabel.INTERNAL_SYSTEM,
            properties={
                "id": "sys-api",
                "name": "Public API Gateway",
                "description": "",
                "category": "API",
                "data_types": ["personal_data"],
            },
        ),
        GraphNode(
            label=NodeLabel.REGULATION,
            properties={
                "id": "reg-impact-demo",
                "title": "Impact demo regulation",
                "jurisdiction": "eu",
                "domain": "security",
                "effective_date": "2026-01-01",
                "source_url": "",
            },
        ),
        GraphNode(
            label=NodeLabel.ARTICLE,
            properties={
                "id": "art-impact-1",
                "number": "1",
                "title": "Logging",
                "text_summary": "Retain access logs.",
                "regulation_id": "reg-impact-demo",
            },
        ),
        GraphNode(
            label=NodeLabel.REQUIREMENT,
            properties={
                "id": "req-impact-1",
                "text": "Retain security logs for 12 months.",
                "obligation_type": "record_keeping",
                "description": "",
            },
        ),
    ],
    edges=[
        GraphEdge(
            source_label=NodeLabel.REGULATION,
            source_id="reg-impact-demo",
            target_label=NodeLabel.JURISDICTION,
            target_id="eu",
            edge_type=EdgeType.APPLIES_IN,
        ),
        GraphEdge(
            source_label=NodeLabel.REGULATION,
            source_id="reg-impact-demo",
            target_label=NodeLabel.ARTICLE,
            target_id="art-impact-1",
            edge_type=EdgeType.CONTAINS,
        ),
        GraphEdge(
            source_label=NodeLabel.ARTICLE,
            source_id="art-impact-1",
            target_label=NodeLabel.REQUIREMENT,
            target_id="req-impact-1",
            edge_type=EdgeType.IMPOSES,
        ),
        GraphEdge(
            source_label=NodeLabel.INTERNAL_SYSTEM,
            source_id="sys-api",
            target_label=NodeLabel.TEAM,
            target_id="team-sec",
            edge_type=EdgeType.OWNED_BY,
        ),
        GraphEdge(
            source_label=NodeLabel.REQUIREMENT,
            source_id="req-impact-1",
            target_label=NodeLabel.INTERNAL_SYSTEM,
            target_id="sys-api",
            edge_type=EdgeType.AFFECTS,
        ),
    ],
)

# ---------------------------------------------------------------------------
# Adversarial / edge (≥5)
# ---------------------------------------------------------------------------

ADV_EMPTY_PAYLOAD = GraphWritePayload(nodes=[], edges=[])

ADV_INVALID_EDGE_TOPOLOGY = GraphWritePayload(
    nodes=[
        GraphNode(label=NodeLabel.REGULATION, properties={"id": "reg-bad", "title": "Bad", "jurisdiction": "eu", "domain": "x"}),
        GraphNode(label=NodeLabel.REGULATION, properties={"id": "reg-bad-2", "title": "Bad2", "jurisdiction": "eu", "domain": "x"}),
    ],
    edges=[
        GraphEdge(
            source_label=NodeLabel.REGULATION,
            source_id="reg-bad",
            target_label=NodeLabel.REGULATION,
            target_id="reg-bad-2",
            edge_type=EdgeType.CONTAINS,
        ),
    ],
)

ADV_DUPLICATE_NODE_IDS_SAME_LABEL = GraphWritePayload(
    nodes=[
        GraphNode(label=NodeLabel.TEAM, properties={"id": "team-dup", "name": "First", "function": "", "contact": ""}),
        GraphNode(label=NodeLabel.TEAM, properties={"id": "team-dup", "name": "Second", "function": "", "contact": ""}),
    ],
    edges=[],
)

ADV_ORPHAN_EDGE_NO_SOURCE_NODE = GraphWritePayload(
    nodes=[
        GraphNode(label=NodeLabel.TEAM, properties={"id": "team-only", "name": "Only Team", "function": "", "contact": ""}),
    ],
    edges=[
        GraphEdge(
            source_label=NodeLabel.INTERNAL_SYSTEM,
            source_id="sys-missing",
            target_label=NodeLabel.TEAM,
            target_id="team-only",
            edge_type=EdgeType.OWNED_BY,
        ),
    ],
)

ADV_SELF_LOOP_AMENDS = GraphWritePayload(
    nodes=[
        GraphNode(
            label=NodeLabel.REGULATION,
            properties={"id": "reg-self", "title": "Self amend", "jurisdiction": "eu", "domain": "test", "source_url": ""},
        ),
    ],
    edges=[
        GraphEdge(
            source_label=NodeLabel.REGULATION,
            source_id="reg-self",
            target_label=NodeLabel.REGULATION,
            target_id="reg-self",
            edge_type=EdgeType.AMENDS,
        ),
    ],
)

ADV_MASS_TEAM_NODES = GraphWritePayload(
    nodes=[
        GraphNode(
            label=NodeLabel.TEAM,
            properties={"id": f"team-bulk-{i}", "name": f"Bulk Team {i}", "function": "", "contact": ""},
        )
        for i in range(150)
    ],
    edges=[],
)
