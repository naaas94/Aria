"""Multi-hop Cypher-based retrieval from the knowledge graph.

Given anchor node IDs (from vector search), expands into the graph
neighborhood to pull structured relational context that vector
similarity alone cannot provide.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from aria.graph.client import Neo4jClient
from aria.graph.queries import execute_named_query

logger = logging.getLogger(__name__)


@dataclass
class GraphContext:
    """Structured context retrieved from graph traversal."""

    anchor_id: str
    anchor_label: str
    neighbors: list[dict[str, Any]] = field(default_factory=list)
    paths: list[dict[str, Any]] = field(default_factory=list)

    @property
    def context_text(self) -> str:
        """Flatten graph context into a text representation for LLM consumption."""
        parts = [f"[Graph anchor: {self.anchor_label} {self.anchor_id}]"]
        for n in self.neighbors:
            parts.append(f"  -> {n}")
        return "\n".join(parts)


class GraphRetriever:
    """Retrieves structured context from Neo4j via named, parameterized queries."""

    def __init__(self, client: Neo4jClient) -> None:
        self._client = client

    async def expand_one_hop(
        self, node_id: str, node_label: str, limit: int = 25
    ) -> GraphContext:
        """Expand one hop from an anchor node."""
        cypher, params = execute_named_query(
            "expand_from_node",
            {"node_id": node_id, "node_label": node_label, "limit": limit},
        )
        rows = await self._client.execute_read(cypher, params)
        return GraphContext(
            anchor_id=node_id,
            anchor_label=node_label,
            neighbors=rows,
        )

    async def expand_two_hops(
        self, node_id: str, node_label: str, limit: int = 50
    ) -> GraphContext:
        """Expand two hops for deeper relational context."""
        cypher, params = execute_named_query(
            "expand_two_hops",
            {"node_id": node_id, "node_label": node_label, "limit": limit},
        )
        rows = await self._client.execute_read(cypher, params)
        return GraphContext(
            anchor_id=node_id,
            anchor_label=node_label,
            paths=rows,
        )

    async def get_regulation_impact(self, regulation_id: str) -> list[dict[str, Any]]:
        """Run the full impact traversal query for a regulation."""
        cypher, params = execute_named_query(
            "impact_by_regulation", {"regulation_id": regulation_id}
        )
        return await self._client.execute_read(cypher, params)

    async def get_uncovered_requirements(self, regulation_id: str) -> list[dict[str, Any]]:
        """Find requirements with no addressing policy."""
        cypher, params = execute_named_query(
            "uncovered_requirements", {"regulation_id": regulation_id}
        )
        return await self._client.execute_read(cypher, params)

    async def get_connected_regulations(self, regulation_id: str) -> list[dict[str, Any]]:
        """Find regulations connected via AMENDS or REFERENCES edges."""
        cypher, params = execute_named_query(
            "connected_regulations", {"regulation_id": regulation_id}
        )
        return await self._client.execute_read(cypher, params)
