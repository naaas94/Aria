"""Factory for full-pipeline ``ingest_document`` callables (extract, graph, vectors).

Wiring is used by the ``aria ingest`` CLI and tests; HTTP ingest routes remain
chunking-only by design.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aria.agents.entity_extractor import EntityExtractorAgent
from aria.agents.graph_builder import GraphBuilderAgent
from aria.contracts.graph_entities import GraphWriteStatus
from aria.contracts.regulation import ExtractedEntities
from aria.graph.client import Neo4jClient
from aria.ingestion.chunker import DocumentChunk
from aria.retrieval.vector_store import VectorStore


@dataclass(frozen=True)
class FullIngestWiring:
    """Async ports for :func:`aria.ingestion.pipeline.ingest_document` full pipeline."""

    entity_extractor: Callable[[str, str], Awaitable[ExtractedEntities]]
    graph_writer: Callable[[ExtractedEntities], Awaitable[GraphWriteStatus]]
    vector_indexer: Callable[[list[DocumentChunk]], Awaitable[bool]]


def build_full_ingest_wiring(
    neo4j: Neo4jClient,
    vector_store: VectorStore,
    *,
    entity_extractor_agent: EntityExtractorAgent | None = None,
    graph_builder_agent: GraphBuilderAgent | None = None,
) -> FullIngestWiring:
    """Create extract / graph / vector closures backed by agents and ``VectorStore``.

    Callers must connect ``neo4j`` (``await connect()``) and ``vector_store`` (``connect()``)
    before invoking the returned callables.
    """
    extractor = entity_extractor_agent or EntityExtractorAgent()
    graph_agent = graph_builder_agent or GraphBuilderAgent(neo4j)

    async def entity_extractor(text: str, content_hash: str) -> ExtractedEntities:
        raw = await extractor.process(
            {"document_text": text, "document_hash": content_hash},
        )
        return ExtractedEntities.model_validate(raw)

    async def graph_writer(entities: ExtractedEntities) -> GraphWriteStatus:
        raw = await graph_agent.process(entities.model_dump())
        return GraphWriteStatus.model_validate(raw)

    async def vector_indexer(chunks: list[DocumentChunk]) -> bool:
        if not chunks:
            return True
        n = await asyncio.to_thread(vector_store.index_chunks, chunks)
        return n == len(chunks)

    return FullIngestWiring(
        entity_extractor=entity_extractor,
        graph_writer=graph_writer,
        vector_indexer=vector_indexer,
    )
