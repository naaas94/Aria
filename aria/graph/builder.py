"""Graph population and update logic with idempotent MERGE operations.

Translates GraphWritePayload (from contracts) into batched Cypher MERGE
statements. Safe to re-run on the same data.
"""

from __future__ import annotations

import logging
from typing import Any

from aria.contracts.graph_entities import (
    EdgeType,
    GraphEdge,
    GraphNode,
    GraphWritePayload,
    GraphWriteStatus,
    NodeLabel,
)
from aria.contracts.regulation import ExtractedEntities, Regulation
from aria.graph.client import Neo4jClient
from aria.graph.schema import NODE_MERGE_KEYS, VALID_EDGES

logger = logging.getLogger(__name__)


def _validate_edge(edge: GraphEdge) -> None:
    """Verify the edge connects valid label/type combinations."""
    triple = (edge.source_label, edge.edge_type, edge.target_label)
    if triple not in VALID_EDGES:
        raise ValueError(
            f"Invalid edge: (:{edge.source_label})-[:{edge.edge_type}]->(:{edge.target_label})"
        )


def _merge_node_cypher(node: GraphNode) -> tuple[str, dict[str, Any]]:
    merge_key = NODE_MERGE_KEYS[node.label]
    merge_val = node.properties[merge_key]
    set_props = {k: v for k, v in node.properties.items() if k != merge_key}

    cypher = (
        f"MERGE (n:{node.label.value} {{{merge_key}: $merge_val}}) "
        f"SET n += $props "
        f"RETURN n.{merge_key} AS id"
    )
    return cypher, {"merge_val": merge_val, "props": set_props}


def _merge_edge_cypher(edge: GraphEdge) -> tuple[str, dict[str, Any]]:
    _validate_edge(edge)
    src_key = NODE_MERGE_KEYS[edge.source_label]
    tgt_key = NODE_MERGE_KEYS[edge.target_label]

    cypher = (
        f"MATCH (a:{edge.source_label.value} {{{src_key}: $src_id}}) "
        f"MATCH (b:{edge.target_label.value} {{{tgt_key}: $tgt_id}}) "
        f"MERGE (a)-[r:{edge.edge_type.value}]->(b) "
        f"SET r += $props "
        f"RETURN type(r) AS rel"
    )
    return cypher, {"src_id": edge.source_id, "tgt_id": edge.target_id, "props": edge.properties}


async def write_payload(client: Neo4jClient, payload: GraphWritePayload) -> GraphWriteStatus:
    """Write a batch of nodes and edges in one Neo4j transaction (commit or full rollback).

    MERGE remains idempotent across separate successful transactions; within one call,
    either all statements commit or none do.
    """
    status = GraphWriteStatus()

    async with client.session() as session:
        tx = await session.begin_transaction()
        try:
            async with tx:
                for node in payload.nodes:
                    cypher, params = _merge_node_cypher(node)
                    result = await tx.run(cypher, params)
                    summary = await result.consume()
                    status.nodes_created += summary.counters.nodes_created
                    status.nodes_merged += max(
                        0, 1 - summary.counters.nodes_created
                    )
                for edge in payload.edges:
                    cypher, params = _merge_edge_cypher(edge)
                    result = await tx.run(cypher, params)
                    summary = await result.consume()
                    status.edges_created += summary.counters.relationships_created
                    status.edges_merged += max(
                        0, 1 - summary.counters.relationships_created
                    )
        except Exception as exc:
            msg = f"Graph write transaction failed: {exc}"
            logger.error(msg)
            return GraphWriteStatus(errors=[msg])

    return status


def entities_to_write_payload(entities: ExtractedEntities) -> GraphWritePayload:
    """Convert ExtractedEntities into a GraphWritePayload for Neo4j.

    Flattens the nested domain model into flat node/edge lists suitable
    for MERGE operations.
    """
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    for jur in entities.jurisdictions:
        nodes.append(GraphNode(label=NodeLabel.JURISDICTION, properties=jur.model_dump()))

    for team in entities.teams:
        nodes.append(GraphNode(label=NodeLabel.TEAM, properties=team.model_dump()))

    for pol in entities.policy_documents:
        props = pol.model_dump()
        owner = props.pop("owner_team", None)
        if props.get("last_reviewed"):
            props["last_reviewed"] = str(props["last_reviewed"])
        nodes.append(GraphNode(label=NodeLabel.POLICY_DOCUMENT, properties=props))
        if owner:
            edges.append(
                GraphEdge(
                    source_label=NodeLabel.POLICY_DOCUMENT,
                    source_id=pol.id,
                    target_label=NodeLabel.TEAM,
                    target_id=owner,
                    edge_type=EdgeType.OWNED_BY,
                )
            )

    for sys in entities.internal_systems:
        props = sys.model_dump()
        owner = props.pop("owner_team", None)
        nodes.append(GraphNode(label=NodeLabel.INTERNAL_SYSTEM, properties=props))
        if owner:
            edges.append(
                GraphEdge(
                    source_label=NodeLabel.INTERNAL_SYSTEM,
                    source_id=sys.id,
                    target_label=NodeLabel.TEAM,
                    target_id=owner,
                    edge_type=EdgeType.OWNED_BY,
                )
            )

    for reg in entities.regulations:
        _add_regulation_nodes_edges(reg, nodes, edges)

    return GraphWritePayload(nodes=nodes, edges=edges)


def _add_regulation_nodes_edges(
    reg: Regulation,
    nodes: list[GraphNode],
    edges: list[GraphEdge],
) -> None:
    reg_props = {
        "id": reg.id,
        "title": reg.title,
        "jurisdiction": reg.jurisdiction,
        "domain": reg.domain,
        "source_url": reg.source_url,
    }
    if reg.effective_date:
        reg_props["effective_date"] = str(reg.effective_date)
    nodes.append(GraphNode(label=NodeLabel.REGULATION, properties=reg_props))

    if reg.jurisdiction:
        edges.append(
            GraphEdge(
                source_label=NodeLabel.REGULATION,
                source_id=reg.id,
                target_label=NodeLabel.JURISDICTION,
                target_id=reg.jurisdiction,
                edge_type=EdgeType.APPLIES_IN,
            )
        )

    for amended_id in reg.amends:
        edges.append(
            GraphEdge(
                source_label=NodeLabel.REGULATION,
                source_id=reg.id,
                target_label=NodeLabel.REGULATION,
                target_id=amended_id,
                edge_type=EdgeType.AMENDS,
            )
        )

    for ref_id in reg.references:
        edges.append(
            GraphEdge(
                source_label=NodeLabel.REGULATION,
                source_id=reg.id,
                target_label=NodeLabel.REGULATION,
                target_id=ref_id,
                edge_type=EdgeType.REFERENCES,
            )
        )

    for article in reg.articles:
        art_props = {
            "id": article.id,
            "number": article.number,
            "title": article.title,
            "text_summary": article.text_summary,
            "regulation_id": article.regulation_id,
        }
        nodes.append(GraphNode(label=NodeLabel.ARTICLE, properties=art_props))
        edges.append(
            GraphEdge(
                source_label=NodeLabel.REGULATION,
                source_id=reg.id,
                target_label=NodeLabel.ARTICLE,
                target_id=article.id,
                edge_type=EdgeType.CONTAINS,
            )
        )

        for req in article.requirements:
            req_props = {
                "id": req.id,
                "text": req.text,
                "obligation_type": req.obligation_type.value,
                "description": req.description,
            }
            if req.deadline:
                req_props["deadline"] = str(req.deadline)
            nodes.append(GraphNode(label=NodeLabel.REQUIREMENT, properties=req_props))
            edges.append(
                GraphEdge(
                    source_label=NodeLabel.ARTICLE,
                    source_id=article.id,
                    target_label=NodeLabel.REQUIREMENT,
                    target_id=req.id,
                    edge_type=EdgeType.IMPOSES,
                )
            )

        for dl in article.deadlines:
            dl_props = {
                "id": dl.id,
                "date": str(dl.date),
                "type": dl.type.value,
                "article_id": dl.article_id,
                "description": dl.description,
            }
            nodes.append(GraphNode(label=NodeLabel.DEADLINE, properties=dl_props))
            edges.append(
                GraphEdge(
                    source_label=NodeLabel.ARTICLE,
                    source_id=article.id,
                    target_label=NodeLabel.DEADLINE,
                    target_id=dl.id,
                    edge_type=EdgeType.HAS_DEADLINE,
                )
            )
