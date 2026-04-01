"""Allow-listed Cypher query library.

All graph reads go through named, parameterized queries here rather than
accepting arbitrary Cypher from callers. This is the safe query surface
exposed via MCP tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CypherQuery:
    name: str
    description: str
    cypher: str
    parameter_names: list[str]


QUERIES: dict[str, CypherQuery] = {}


def _register(q: CypherQuery) -> CypherQuery:
    QUERIES[q.name] = q
    return q


# ---------------------------------------------------------------------------
# Regulation queries
# ---------------------------------------------------------------------------

GET_REGULATION_BY_ID = _register(
    CypherQuery(
        name="get_regulation_by_id",
        description="Fetch a single regulation by its ID",
        cypher="MATCH (r:Regulation {id: $regulation_id}) RETURN r",
        parameter_names=["regulation_id"],
    )
)

GET_REGULATION_ARTICLES = _register(
    CypherQuery(
        name="get_regulation_articles",
        description="List all articles belonging to a regulation",
        cypher=(
            "MATCH (r:Regulation {id: $regulation_id})-[:CONTAINS]->(a:Article) "
            "RETURN a ORDER BY a.number"
        ),
        parameter_names=["regulation_id"],
    )
)

LIST_REGULATIONS = _register(
    CypherQuery(
        name="list_regulations",
        description="List all regulations in the graph",
        cypher="MATCH (r:Regulation) RETURN r ORDER BY r.title",
        parameter_names=[],
    )
)

# ---------------------------------------------------------------------------
# Multi-hop compliance queries
# ---------------------------------------------------------------------------

UNCOVERED_REQUIREMENTS = _register(
    CypherQuery(
        name="uncovered_requirements",
        description=(
            "Find requirements from a regulation that affect internal systems "
            "but have no addressing policy document"
        ),
        cypher=(
            "MATCH (r:Regulation {id: $regulation_id})-[:CONTAINS]->(a:Article)"
            "-[:IMPOSES]->(req:Requirement)-[:AFFECTS]->(sys:InternalSystem)"
            "-[:OWNED_BY]->(t:Team) "
            "WHERE NOT (req)-[:ADDRESSED_BY]->(:PolicyDocument) "
            "RETURN r.title AS regulation, a.number AS article, "
            "req.text AS requirement, req.obligation_type AS obligation_type, "
            "sys.name AS system, t.name AS team "
            "ORDER BY a.number"
        ),
        parameter_names=["regulation_id"],
    )
)

IMPACT_BY_REGULATION = _register(
    CypherQuery(
        name="impact_by_regulation",
        description="Full impact chain: regulation -> articles -> requirements -> systems -> teams",
        cypher=(
            "MATCH (r:Regulation {id: $regulation_id})-[:CONTAINS]->(a:Article)"
            "-[:IMPOSES]->(req:Requirement)-[:AFFECTS]->(sys:InternalSystem)"
            "-[:OWNED_BY]->(t:Team) "
            "OPTIONAL MATCH (req)-[:ADDRESSED_BY]->(pol:PolicyDocument) "
            "RETURN r.title AS regulation, a.number AS article, a.id AS article_id, "
            "req.id AS requirement_id, req.text AS requirement, "
            "req.obligation_type AS obligation_type, "
            "sys.id AS system_id, sys.name AS system_name, "
            "t.name AS team, t.id AS team_id, "
            "pol.id AS policy_id, pol.title AS policy_title "
            "ORDER BY a.number"
        ),
        parameter_names=["regulation_id"],
    )
)

REQUIREMENTS_BY_TEAM = _register(
    CypherQuery(
        name="requirements_by_team",
        description="All requirements affecting systems owned by a specific team",
        cypher=(
            "MATCH (req:Requirement)-[:AFFECTS]->(sys:InternalSystem)"
            "-[:OWNED_BY]->(t:Team {id: $team_id}) "
            "OPTIONAL MATCH (req)<-[:IMPOSES]-(a:Article)<-[:CONTAINS]-(r:Regulation) "
            "RETURN req.id AS requirement_id, req.text AS requirement, "
            "sys.name AS system, r.title AS regulation, a.number AS article "
            "ORDER BY r.title, a.number"
        ),
        parameter_names=["team_id"],
    )
)

DEADLINES_BY_REGULATION = _register(
    CypherQuery(
        name="deadlines_by_regulation",
        description="All deadlines for articles in a regulation",
        cypher=(
            "MATCH (r:Regulation {id: $regulation_id})-[:CONTAINS]->(a:Article)"
            "-[:HAS_DEADLINE]->(d:Deadline) "
            "RETURN a.number AS article, d.date AS deadline_date, "
            "d.type AS deadline_type, d.description AS description "
            "ORDER BY d.date"
        ),
        parameter_names=["regulation_id"],
    )
)

# ---------------------------------------------------------------------------
# Graph neighborhood expansion (used by GraphRAG retrieval)
# ---------------------------------------------------------------------------

EXPAND_FROM_NODE = _register(
    CypherQuery(
        name="expand_from_node",
        description="Expand one hop from a node by label and ID",
        cypher=(
            "MATCH (n {id: $node_id}) "
            "WHERE $node_label IN labels(n) "
            "OPTIONAL MATCH (n)-[r]-(neighbor) "
            "RETURN n, type(r) AS rel_type, neighbor "
            "LIMIT $limit"
        ),
        parameter_names=["node_id", "node_label", "limit"],
    )
)

EXPAND_TWO_HOPS = _register(
    CypherQuery(
        name="expand_two_hops",
        description="Expand two hops from a node for deeper context",
        cypher=(
            "MATCH (n {id: $node_id}) "
            "WHERE $node_label IN labels(n) "
            "OPTIONAL MATCH path = (n)-[*1..2]-(neighbor) "
            "RETURN nodes(path) AS nodes, relationships(path) AS rels "
            "LIMIT $limit"
        ),
        parameter_names=["node_id", "node_label", "limit"],
    )
)

CONNECTED_REGULATIONS = _register(
    CypherQuery(
        name="connected_regulations",
        description="Find regulations connected via AMENDS or REFERENCES edges",
        cypher=(
            "MATCH (r:Regulation {id: $regulation_id})"
            "-[:AMENDS|REFERENCES*1..2]-(related:Regulation) "
            "RETURN DISTINCT related.id AS id, related.title AS title, "
            "related.jurisdiction AS jurisdiction"
        ),
        parameter_names=["regulation_id"],
    )
)


def execute_named_query(
    query_name: str, parameters: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Resolve a named query and validate parameters.

    Returns the Cypher string and validated parameter dict, ready for
    the Neo4j driver. Raises KeyError for unknown queries and ValueError
    for missing parameters.
    """
    if query_name not in QUERIES:
        raise KeyError(f"Unknown query: {query_name!r}. Available: {sorted(QUERIES)}")

    q = QUERIES[query_name]
    missing = [p for p in q.parameter_names if p not in parameters]
    if missing:
        raise ValueError(f"Query {query_name!r} missing parameters: {missing}")

    filtered = {k: v for k, v in parameters.items() if k in q.parameter_names}
    return q.cypher, filtered
