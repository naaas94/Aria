"""Graph-level node and edge schema models.

Maps domain contracts to Neo4j property graph primitives. Used by the graph
builder for MERGE operations and by MCP tools for query result typing.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from aria.contracts._strict import enforce_schema_version_if_configured

SCHEMA_VERSION = "0.1.0"


class NodeLabel(StrEnum):
    REGULATION = "Regulation"
    ARTICLE = "Article"
    REQUIREMENT = "Requirement"
    POLICY_DOCUMENT = "PolicyDocument"
    INTERNAL_SYSTEM = "InternalSystem"
    TEAM = "Team"
    JURISDICTION = "Jurisdiction"
    DEADLINE = "Deadline"


class EdgeType(StrEnum):
    CONTAINS = "CONTAINS"
    IMPOSES = "IMPOSES"
    AMENDS = "AMENDS"
    REFERENCES = "REFERENCES"
    APPLIES_IN = "APPLIES_IN"
    AFFECTS = "AFFECTS"
    ADDRESSED_BY = "ADDRESSED_BY"
    OWNED_BY = "OWNED_BY"
    HAS_DEADLINE = "HAS_DEADLINE"


class GraphNode(BaseModel):
    """A single node to be written to (or read from) Neo4j."""

    label: NodeLabel
    properties: dict[str, Any] = Field(
        ..., description="Node properties; must include 'id' as the merge key"
    )

    @property
    def merge_key(self) -> str:
        rid = self.properties["id"]
        return rid if isinstance(rid, str) else str(rid)


class GraphEdge(BaseModel):
    """A single directed edge to be written to (or read from) Neo4j."""

    source_label: NodeLabel
    source_id: str
    target_label: NodeLabel
    target_id: str
    edge_type: EdgeType
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphWritePayload(BaseModel):
    """Batch of nodes and edges committed in one Neo4j transaction by ``write_payload``."""

    schema_version: str = SCHEMA_VERSION
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _strict_schema_version(self) -> GraphWritePayload:
        enforce_schema_version_if_configured(self)
        return self


class GraphWriteStatus(BaseModel):
    """Result of a graph write operation."""

    nodes_created: int = 0
    nodes_merged: int = 0
    edges_created: int = 0
    edges_merged: int = 0
    errors: list[str] = Field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class GraphQueryResult(BaseModel):
    """Typed wrapper around a Cypher query result set."""

    columns: list[str]
    rows: list[dict[str, Any]]
    query_time_ms: float = 0.0
