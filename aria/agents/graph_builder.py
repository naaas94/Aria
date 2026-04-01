"""Graph builder agent — translates extracted entities into graph writes.

Receives validated entity payloads from the entity extractor and
converts them to idempotent Cypher MERGE operations via the graph builder.
"""

from __future__ import annotations

from typing import Any

from aria.agents.base import BaseAgent
from aria.contracts.graph_entities import GraphWriteStatus
from aria.contracts.regulation import ExtractedEntities
from aria.graph.builder import entities_to_write_payload, write_payload
from aria.graph.client import Neo4jClient


class GraphBuilderAgent(BaseAgent):
    name = "graph_builder"

    def __init__(self, neo4j_client: Neo4jClient | None = None) -> None:
        super().__init__()
        self._client = neo4j_client

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        entities = ExtractedEntities.model_validate(input_data)
        payload = entities_to_write_payload(entities)

        self.logger.info(
            "Building graph: %d nodes, %d edges",
            len(payload.nodes), len(payload.edges),
        )

        if self._client:
            status = await write_payload(self._client, payload)
        else:
            self.logger.warning("No Neo4j client configured — returning dry-run status")
            status = GraphWriteStatus(
                nodes_created=len(payload.nodes),
                edges_created=len(payload.edges),
            )

        return status.model_dump()
