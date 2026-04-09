"""MCP server exposing tools to agents via structured JSON requests.

Implements the tool discovery and invocation protocol. All graph access
goes through named queries — no arbitrary Cypher execution.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from aria.graph.client import Neo4jClient
from aria.observability.metrics import MCP_TOOL_CALL_COUNTER, MCP_TOOL_CALL_DURATION
from aria.graph.queries import execute_named_query
from aria.protocols.mcp.tools import (
    TOOL_DEFINITIONS,
    CypherQueryInput,
    HybridRetrievalInput,
    RegulationFetchInput,
    ToolDefinition,
    ToolResult,
    VectorSearchInput,
)
from aria.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)


class MCPServer:
    """Local MCP tool server.

    In a production deployment this would run as a sidecar process
    with HTTP transport. For local development it operates in-process
    with the same interface contract.
    """

    def __init__(
        self,
        neo4j_client: Neo4jClient | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self._neo4j = neo4j_client
        self._vector_store = vector_store
        self._handlers: dict[str, Any] = {
            "graph_query": self._handle_graph_query,
            "vector_search": self._handle_vector_search,
            "hybrid_retrieve": self._handle_hybrid_retrieve,
            "fetch_regulation": self._handle_fetch_regulation,
        }

    def list_tools(self) -> list[ToolDefinition]:
        """Tool discovery — returns metadata for all available tools."""
        return list(TOOL_DEFINITIONS)

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """Invoke a tool by name with validated arguments."""
        start = time.monotonic()

        handler = self._handlers.get(tool_name)
        if not handler:
            MCP_TOOL_CALL_COUNTER.labels(tool_name=tool_name, status="error").inc()
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error="Unknown tool name.",
                error_code="MCP_UNKNOWN_TOOL",
            )

        try:
            data = await handler(arguments)
            elapsed_s = time.monotonic() - start
            logger.info("MCP tool %s completed in %.1fms", tool_name, elapsed_s * 1000)
            MCP_TOOL_CALL_COUNTER.labels(tool_name=tool_name, status="success").inc()
            MCP_TOOL_CALL_DURATION.labels(tool_name=tool_name).observe(elapsed_s)
            return ToolResult(tool_name=tool_name, success=True, data=data)
        except Exception:
            logger.exception("MCP tool %s failed", tool_name)
            MCP_TOOL_CALL_COUNTER.labels(tool_name=tool_name, status="error").inc()
            MCP_TOOL_CALL_DURATION.labels(tool_name=tool_name).observe(time.monotonic() - start)
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error="Tool execution failed. See server logs for details.",
                error_code="MCP_TOOL_EXECUTION_FAILED",
            )

    async def _handle_graph_query(self, arguments: dict[str, Any]) -> Any:
        validated = CypherQueryInput.model_validate(arguments)
        cypher, params = execute_named_query(validated.query_name, validated.parameters)

        if not self._neo4j:
            raise RuntimeError("Neo4j client not configured")

        return await self._neo4j.execute_read(cypher, params)

    async def _handle_vector_search(self, arguments: dict[str, Any]) -> Any:
        validated = VectorSearchInput.model_validate(arguments)

        if not self._vector_store:
            raise RuntimeError("Vector store not configured")

        results = self._vector_store.search(validated.query_text, top_k=validated.top_k)
        return [
            {
                "chunk_id": r.chunk_id,
                "text": r.text,
                "score": r.score,
                "metadata": r.metadata,
            }
            for r in results
        ]

    async def _handle_hybrid_retrieve(self, arguments: dict[str, Any]) -> Any:
        validated = HybridRetrievalInput.model_validate(arguments)

        if not self._vector_store:
            raise RuntimeError("Vector store not configured")
        if not self._neo4j:
            raise RuntimeError("Neo4j client not configured")

        from aria.retrieval.graph_retriever import GraphRetriever
        from aria.retrieval.hybrid_retriever import HybridRetriever

        graph_retriever = GraphRetriever(self._neo4j)
        hybrid = HybridRetriever(
            self._vector_store, graph_retriever,
            vector_top_k=validated.vector_top_k,
            graph_hops=validated.graph_hops,
        )
        result = await hybrid.retrieve(
            validated.query_text, node_label_hint=validated.node_label_hint
        )
        return {
            "context": result.context_text,
            "trace": result.trace,
        }

    async def _handle_fetch_regulation(self, arguments: dict[str, Any]) -> Any:
        validated = RegulationFetchInput.model_validate(arguments)

        if not self._neo4j:
            raise RuntimeError("Neo4j client not configured")

        reg_rows = await self._neo4j.execute_read(
            *execute_named_query("get_regulation_by_id", {"regulation_id": validated.regulation_id})
        )
        articles = await self._neo4j.execute_read(
            *execute_named_query("get_regulation_articles", {"regulation_id": validated.regulation_id})
        )

        return {
            "regulation": reg_rows[0] if reg_rows else None,
            "articles": articles,
        }


class MCPToolPortsAdapter:
    """Adapts the MCP server into the ToolPorts interface used by orchestration nodes.

    This bridges the gap between the MCP protocol layer and the
    orchestration engine, which programs against the ToolPorts protocol.
    """

    def __init__(self, mcp_server: MCPServer, llm_generate_fn: Any | None = None) -> None:
        self._mcp = mcp_server
        self._llm_fn = llm_generate_fn

    async def extract_entities(self, text: str, doc_hash: str) -> dict:
        from aria.agents.entity_extractor import EntityExtractorAgent
        agent = EntityExtractorAgent()
        return await agent.process({"document_text": text, "document_hash": doc_hash})

    async def write_to_graph(self, entities: dict) -> dict:
        from aria.agents.graph_builder import GraphBuilderAgent
        agent = GraphBuilderAgent()
        return await agent.process(entities)

    async def index_vectors(self, chunks: list[dict]) -> bool:
        return True

    async def query_graph(self, query_name: str, params: dict) -> list[dict]:
        result = await self._mcp.call_tool("graph_query", {
            "query_name": query_name,
            "parameters": params,
        })
        if not result.success:
            raise RuntimeError(result.error)
        return result.data

    async def vector_search(self, query: str, top_k: int = 10) -> list[dict]:
        result = await self._mcp.call_tool("vector_search", {
            "query_text": query,
            "top_k": top_k,
        })
        if not result.success:
            raise RuntimeError(result.error)
        return result.data

    async def generate_text(self, messages: list[dict]) -> str:
        if self._llm_fn:
            return await self._llm_fn(messages)
        from aria.llm.client import LLMClient
        client = LLMClient()
        return await client.complete(messages)
