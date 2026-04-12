"""Unit tests for ``aria.ingestion.wiring`` (no live Neo4j/Chroma/LLM)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from aria.contracts.regulation import ExtractedEntities
from aria.ingestion.chunker import DocumentChunk
from aria.ingestion.wiring import build_full_ingest_wiring


@pytest.mark.asyncio
async def test_vector_indexer_empty_returns_true_without_index_chunks() -> None:
    neo = MagicMock()
    vs = MagicMock()
    wiring = build_full_ingest_wiring(neo, vs)
    assert await wiring.vector_indexer([]) is True
    vs.index_chunks.assert_not_called()


@pytest.mark.asyncio
async def test_vector_indexer_uses_to_thread_and_checks_count() -> None:
    neo = MagicMock()
    vs = MagicMock()
    vs.index_chunks.return_value = 2
    chunks = [
        DocumentChunk(chunk_id="a", text="t1", source_document_hash="h1"),
        DocumentChunk(chunk_id="b", text="t2", source_document_hash="h1"),
    ]
    wiring = build_full_ingest_wiring(neo, vs)
    ok = await wiring.vector_indexer(chunks)
    assert ok is True
    vs.index_chunks.assert_called_once_with(chunks)


@pytest.mark.asyncio
async def test_vector_indexer_false_when_partial_index() -> None:
    neo = MagicMock()
    vs = MagicMock()
    vs.index_chunks.return_value = 1
    chunks = [
        DocumentChunk(chunk_id="a", text="t1", source_document_hash="h1"),
        DocumentChunk(chunk_id="b", text="t2", source_document_hash="h1"),
    ]
    wiring = build_full_ingest_wiring(neo, vs)
    assert await wiring.vector_indexer(chunks) is False


@pytest.mark.asyncio
async def test_entity_extractor_closure_validates_agent_output() -> None:
    neo = MagicMock()
    vs = MagicMock()
    entities = ExtractedEntities(source_document_hash="x" * 64)
    mock_agent = MagicMock()
    mock_agent.process = AsyncMock(return_value=entities.model_dump())
    wiring = build_full_ingest_wiring(
        neo,
        vs,
        entity_extractor_agent=mock_agent,
        graph_builder_agent=MagicMock(),
    )
    out = await wiring.entity_extractor("hello", "hash1")
    assert out.source_document_hash == entities.source_document_hash
    mock_agent.process.assert_awaited_once_with(
        {"document_text": "hello", "document_hash": "hash1"},
    )


@pytest.mark.asyncio
async def test_graph_writer_closure() -> None:
    from aria.contracts.graph_entities import GraphWriteStatus

    neo = MagicMock()
    vs = MagicMock()
    entities = ExtractedEntities(source_document_hash="y" * 64)
    gb = MagicMock()
    gb.process = AsyncMock(
        return_value=GraphWriteStatus(nodes_merged=1, edges_merged=0).model_dump(),
    )
    wiring = build_full_ingest_wiring(
        neo,
        vs,
        entity_extractor_agent=MagicMock(),
        graph_builder_agent=gb,
    )
    status = await wiring.graph_writer(entities)
    assert status.success is True
    gb.process.assert_awaited_once()
