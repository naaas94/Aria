"""Integration tests for the ingestion pipeline.

Tests idempotency, duplicate detection, partial failure recovery,
and the full parse-chunk-extract flow.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria.ingestion.chunker import chunk_text
from aria.ingestion.parsers.html_parser import parse_html
from aria.ingestion.pipeline import (
    IngestionStatus,
    ingest_document,
    reset_ingestion_state,
)

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Test Regulation</title></head>
<body>
<h1>Article 1 — Scope</h1>
<p>This regulation applies to all AI systems placed on the market.
Organizations must classify their systems according to risk categories.
High-risk systems require conformity assessment before deployment.</p>
<h2>Section 1.1 — Definitions</h2>
<p>An AI system means software that is developed with machine learning approaches.
The provider is the entity that develops or commissions an AI system.</p>
<h1>Article 2 — Obligations</h1>
<p>Providers of high-risk AI systems shall establish a risk management system.
The risk management system shall be a continuous iterative process.
It shall include identification of foreseeable risks and estimation of risks.</p>
</body>
</html>
"""


@pytest.fixture(autouse=True)
def _clean_state():
    reset_ingestion_state()
    yield
    reset_ingestion_state()


class TestHTMLParsing:
    def test_parse_html_string(self):
        doc = parse_html(SAMPLE_HTML, is_file=False)
        assert doc.title == "Test Regulation"
        assert len(doc.sections) > 0
        assert doc.content_hash

    def test_parse_html_file(self, tmp_path: Path):
        html_file = tmp_path / "reg.html"
        html_file.write_text(SAMPLE_HTML)
        doc = parse_html(html_file)
        assert doc.title == "Test Regulation"
        assert doc.content_hash

    def test_content_hash_deterministic(self):
        doc1 = parse_html(SAMPLE_HTML, is_file=False)
        doc2 = parse_html(SAMPLE_HTML, is_file=False)
        assert doc1.content_hash == doc2.content_hash


class TestChunking:
    def test_basic_chunking(self):
        text = "This is a test sentence. " * 200
        chunks = chunk_text(text, source_hash="abc123", chunk_size=100)
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.chunk_id
            assert chunk.source_document_hash == "abc123"

    def test_chunk_ids_unique(self):
        text = "Sentence one is here. " * 300
        chunks = chunk_text(text, source_hash="hash1", chunk_size=50)
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_empty_text_produces_no_chunks(self):
        chunks = chunk_text("", source_hash="empty")
        assert chunks == []

    def test_metadata_preserved(self):
        text = "A regulatory requirement that must be met. " * 50
        chunks = chunk_text(text, source_hash="h", metadata={"source": "test.pdf"})
        assert all(c.metadata.get("source") == "test.pdf" for c in chunks)


class TestIngestionPipeline:
    @pytest.mark.asyncio
    async def test_ingest_html_document(self, tmp_path: Path):
        html_file = tmp_path / "regulation.html"
        html_file.write_text(SAMPLE_HTML)
        result = await ingest_document(html_file)
        assert result.status == IngestionStatus.SUCCESS
        assert result.document_hash
        assert result.chunks_produced > 0

    @pytest.mark.asyncio
    async def test_duplicate_detection(self, tmp_path: Path):
        html_file = tmp_path / "regulation.html"
        html_file.write_text(SAMPLE_HTML)
        r1 = await ingest_document(html_file)
        assert r1.status == IngestionStatus.SUCCESS

        r2 = await ingest_document(html_file)
        assert r2.status == IngestionStatus.SKIPPED_DUPLICATE

    @pytest.mark.asyncio
    async def test_force_reingest(self, tmp_path: Path):
        html_file = tmp_path / "regulation.html"
        html_file.write_text(SAMPLE_HTML)
        await ingest_document(html_file)
        result = await ingest_document(html_file, force=True)
        assert result.status == IngestionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_unsupported_format(self, tmp_path: Path):
        bad_file = tmp_path / "document.docx"
        bad_file.write_text("not a real docx")
        result = await ingest_document(bad_file)
        assert result.status == IngestionStatus.PARSE_ERROR

    @pytest.mark.asyncio
    async def test_missing_file(self):
        result = await ingest_document("/nonexistent/file.pdf")
        assert result.status == IngestionStatus.PARSE_ERROR


class TestNeo4jIngestionDedup:
    """Durable idempotency hooks (mocked Neo4j client)."""

    @pytest.mark.asyncio
    async def test_hydrated_complete_hash_skips_without_upsert(self, tmp_path: Path) -> None:
        html_file = tmp_path / "regulation.html"
        html_file.write_text(SAMPLE_HTML)
        content_hash = parse_html(SAMPLE_HTML, is_file=False).content_hash
        mock_neo = MagicMock()

        with (
            patch(
                "aria.ingestion.pipeline.is_pipeline_complete",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "aria.ingestion.pipeline.upsert_ingestion_progress",
                new_callable=AsyncMock,
            ) as up,
        ):
            result = await ingest_document(html_file, neo4j_dedup=mock_neo)

        assert result.status == IngestionStatus.SKIPPED_DUPLICATE
        up.assert_not_called()

    @pytest.mark.asyncio
    async def test_success_calls_upsert_with_pipeline_complete(self, tmp_path: Path) -> None:
        html_file = tmp_path / "regulation.html"
        html_file.write_text(SAMPLE_HTML)
        mock_neo = MagicMock()

        with (
            patch(
                "aria.ingestion.pipeline.is_pipeline_complete",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "aria.ingestion.pipeline.upsert_ingestion_progress",
                new_callable=AsyncMock,
            ) as up,
        ):
            result = await ingest_document(html_file, neo4j_dedup=mock_neo)

        assert result.status == IngestionStatus.SUCCESS
        up.assert_awaited_once()
        _client_arg, hash_arg = up.call_args[0]
        assert hash_arg == result.document_hash
        assert up.call_args[1]["pipeline_complete"] is True
        assert up.call_args[1]["graph_indexed"] is True
        assert up.call_args[1]["vector_indexed"] is True
