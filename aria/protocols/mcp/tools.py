"""MCP tool definitions: graph query, vector search, hybrid retrieval, doc fetch.

Each tool has a Pydantic input schema, a handler function, and metadata.
Tools enforce the allow-listed query surface — no arbitrary Cypher.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from aria.graph.queries import QUERIES


class CypherQueryInput(BaseModel):
    """Input for the graph_query tool — restricted to named queries only."""

    query_name: str = Field(
        ...,
        description=f"Named query to execute. Available: {sorted(QUERIES.keys())}",
    )
    parameters: dict[str, Any] = Field(default_factory=dict)


class VectorSearchInput(BaseModel):
    query_text: str = Field(..., description="Natural language query for semantic search")
    top_k: int = Field(default=10, ge=1, le=50)


class HybridRetrievalInput(BaseModel):
    query_text: str = Field(..., description="Natural language compliance query")
    vector_top_k: int = Field(default=10, ge=1, le=50)
    graph_hops: int = Field(default=1, ge=1, le=2)
    node_label_hint: str = Field(default="Article")


class RegulationFetchInput(BaseModel):
    regulation_id: str = Field(..., description="ID of the regulation to fetch")


class ToolResult(BaseModel):
    """Standard result envelope for all MCP tool calls."""

    tool_name: str
    success: bool
    data: Any = None
    error: str | None = None
    error_code: str | None = None


class ToolDefinition(BaseModel):
    """Metadata describing a single MCP tool."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] = Field(
        default_factory=lambda: ToolResult.model_json_schema(),
        description="JSON Schema for the ToolResult envelope returned by call_tool (data is tool-specific).",
    )


TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="graph_query",
        description="Execute a named, parameterized Cypher read query against the Neo4j knowledge graph",
        input_schema=CypherQueryInput.model_json_schema(),
    ),
    ToolDefinition(
        name="vector_search",
        description="Semantic search over regulatory document chunks in ChromaDB",
        input_schema=VectorSearchInput.model_json_schema(),
    ),
    ToolDefinition(
        name="hybrid_retrieve",
        description="Combined graph traversal + vector search with result fusion",
        input_schema=HybridRetrievalInput.model_json_schema(),
    ),
    ToolDefinition(
        name="fetch_regulation",
        description="Retrieve full regulation metadata and article list by ID",
        input_schema=RegulationFetchInput.model_json_schema(),
    ),
]
