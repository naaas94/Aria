"""Neo4j node and edge type definitions with constraint and index DDL.

Provides the Cypher statements needed to initialize the graph schema
(uniqueness constraints and indexes) and maps domain contracts to graph labels.
"""

from __future__ import annotations

from aria.contracts.graph_entities import EdgeType, NodeLabel

NODE_MERGE_KEYS: dict[NodeLabel, str] = {
    NodeLabel.REGULATION: "id",
    NodeLabel.ARTICLE: "id",
    NodeLabel.REQUIREMENT: "id",
    NodeLabel.POLICY_DOCUMENT: "id",
    NodeLabel.INTERNAL_SYSTEM: "id",
    NodeLabel.TEAM: "id",
    NodeLabel.JURISDICTION: "id",
    NodeLabel.DEADLINE: "id",
}

VALID_EDGES: list[tuple[NodeLabel, EdgeType, NodeLabel]] = [
    (NodeLabel.REGULATION, EdgeType.CONTAINS, NodeLabel.ARTICLE),
    (NodeLabel.ARTICLE, EdgeType.IMPOSES, NodeLabel.REQUIREMENT),
    (NodeLabel.REGULATION, EdgeType.AMENDS, NodeLabel.REGULATION),
    (NodeLabel.REGULATION, EdgeType.REFERENCES, NodeLabel.REGULATION),
    (NodeLabel.REGULATION, EdgeType.APPLIES_IN, NodeLabel.JURISDICTION),
    (NodeLabel.REQUIREMENT, EdgeType.AFFECTS, NodeLabel.INTERNAL_SYSTEM),
    (NodeLabel.REQUIREMENT, EdgeType.ADDRESSED_BY, NodeLabel.POLICY_DOCUMENT),
    (NodeLabel.POLICY_DOCUMENT, EdgeType.OWNED_BY, NodeLabel.TEAM),
    (NodeLabel.INTERNAL_SYSTEM, EdgeType.OWNED_BY, NodeLabel.TEAM),
    (NodeLabel.ARTICLE, EdgeType.HAS_DEADLINE, NodeLabel.DEADLINE),
]


def generate_constraint_statements() -> list[str]:
    """Produce Cypher CREATE CONSTRAINT statements for all node merge keys."""
    stmts: list[str] = []
    for label, key in NODE_MERGE_KEYS.items():
        name = f"unique_{label.value.lower()}_{key}"
        stmts.append(
            f"CREATE CONSTRAINT {name} IF NOT EXISTS "
            f"FOR (n:{label.value}) REQUIRE n.{key} IS UNIQUE"
        )
    stmts.append(
        "CREATE CONSTRAINT ingestion_record_content_hash IF NOT EXISTS "
        "FOR (r:IngestionRecord) REQUIRE r.content_hash IS UNIQUE"
    )
    return stmts


def generate_index_statements() -> list[str]:
    """Produce supplementary indexes for common query patterns."""
    return [
        "CREATE INDEX reg_title IF NOT EXISTS FOR (n:Regulation) ON (n.title)",
        "CREATE INDEX article_number IF NOT EXISTS FOR (n:Article) ON (n.number)",
        "CREATE INDEX req_obligation IF NOT EXISTS FOR (n:Requirement) ON (n.obligation_type)",
        "CREATE INDEX system_category IF NOT EXISTS FOR (n:InternalSystem) ON (n.category)",
        "CREATE INDEX team_name IF NOT EXISTS FOR (n:Team) ON (n.name)",
    ]
