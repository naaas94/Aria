"""Unit tests for the Cypher query library and graph entity contracts."""

from __future__ import annotations

import pytest

from aria.contracts.graph_entities import (
    EdgeType,
    GraphEdge,
    GraphNode,
    GraphWritePayload,
    GraphWriteStatus,
    NodeLabel,
)
from aria.graph.queries import QUERIES, execute_named_query
from aria.graph.schema import VALID_EDGES, generate_constraint_statements


class TestNamedQueries:
    def test_all_queries_registered(self):
        assert len(QUERIES) > 0
        for name, q in QUERIES.items():
            assert q.name == name
            assert q.cypher
            assert isinstance(q.parameter_names, list)

    def test_execute_known_query(self):
        cypher, params = execute_named_query(
            "get_regulation_by_id", {"regulation_id": "reg-gdpr"}
        )
        assert "Regulation" in cypher
        assert params == {"regulation_id": "reg-gdpr"}

    def test_execute_unknown_query_raises(self):
        with pytest.raises(KeyError, match="Unknown query"):
            execute_named_query("nonexistent_query", {})

    def test_missing_parameter_raises(self):
        with pytest.raises(ValueError, match="missing parameters"):
            execute_named_query("get_regulation_by_id", {})

    def test_extra_parameters_filtered(self):
        _, params = execute_named_query(
            "get_regulation_by_id",
            {"regulation_id": "reg-gdpr", "extra_param": "ignored"},
        )
        assert "extra_param" not in params

    def test_parameterless_query(self):
        cypher, params = execute_named_query("list_regulations", {})
        assert "Regulation" in cypher
        assert params == {}


class TestSchemaGeneration:
    def test_constraint_statements_generated(self):
        stmts = generate_constraint_statements()
        assert len(stmts) == len(NodeLabel)
        for stmt in stmts:
            assert stmt.startswith("CREATE CONSTRAINT")
            assert "IF NOT EXISTS" in stmt

    def test_valid_edges_cover_all_edge_types(self):
        used_types = {e[1] for e in VALID_EDGES}
        assert used_types == set(EdgeType)


class TestGraphContracts:
    def test_graph_node_merge_key(self):
        node = GraphNode(
            label=NodeLabel.REGULATION,
            properties={"id": "reg-1", "title": "Test"},
        )
        assert node.merge_key == "reg-1"

    def test_graph_write_status_success(self):
        status = GraphWriteStatus(nodes_created=5, edges_created=3)
        assert status.success is True

    def test_graph_write_status_failure(self):
        status = GraphWriteStatus(errors=["something broke"])
        assert status.success is False

    def test_write_payload_serialization(self):
        payload = GraphWritePayload(
            nodes=[
                GraphNode(label=NodeLabel.TEAM, properties={"id": "t1", "name": "Eng"})
            ],
            edges=[
                GraphEdge(
                    source_label=NodeLabel.INTERNAL_SYSTEM,
                    source_id="sys-1",
                    target_label=NodeLabel.TEAM,
                    target_id="t1",
                    edge_type=EdgeType.OWNED_BY,
                )
            ],
        )
        data = payload.model_dump()
        assert len(data["nodes"]) == 1
        assert len(data["edges"]) == 1
