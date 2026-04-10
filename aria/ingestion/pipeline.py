"""End-to-end ingestion orchestrator.

Coordinates parsing, chunking, entity extraction, graph writing, and
vector indexing with idempotency guarantees. A document that has already
been ingested (same content hash) is skipped unless forced.

Without ``neo4j_dedup``, deduplication is in-process only (``_ingested_hashes``)
and is lost on restart. With a connected ``Neo4jClient``, each candidate hash is
checked against ``(:IngestionRecord)`` (point lookups, not a full-table load) so
skips survive restarts; partial runs store ``pipeline_complete=false`` for ops visibility.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from aria.contracts.regulation import ExtractedEntities
from aria.graph.client import Neo4jClient
from aria.graph.ingestion_record import is_pipeline_complete, upsert_ingestion_progress
from aria.ingestion.chunker import DocumentChunk, chunk_text
from aria.ingestion.parsers.html_parser import ParsedHTMLDocument, parse_html
from aria.ingestion.parsers.pdf_parser import ParsedDocument, parse_pdf

logger = logging.getLogger(__name__)


class DocumentFormat(StrEnum):
    PDF = "pdf"
    HTML = "html"


class IngestionStatus(StrEnum):
    SUCCESS = "success"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    PARSE_ERROR = "parse_error"
    EXTRACTION_ERROR = "extraction_error"
    GRAPH_WRITE_ERROR = "graph_write_error"
    VECTOR_INDEX_ERROR = "vector_index_error"
    PARTIAL_FAILURE = "partial_failure"


@dataclass
class IngestionResult:
    status: IngestionStatus
    document_hash: str = ""
    chunks_produced: int = 0
    entities_extracted: bool = False
    graph_written: bool = False
    vector_indexed: bool = False
    errors: list[str] = field(default_factory=list)


_ingested_hashes: set[str] = set()


async def _ensure_neo4j_dedup_for_hash(client: Neo4jClient, content_hash: str) -> None:
    """If this hash completed the pipeline in Neo4j, add it to the in-memory skip set."""
    try:
        if await is_pipeline_complete(client, content_hash):
            _ingested_hashes.add(content_hash)
    except Exception as exc:
        logger.warning("Could not check ingestion dedup in Neo4j: %s", exc)


def _detect_format(path: Path) -> DocumentFormat:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return DocumentFormat.PDF
    if suffix in (".html", ".htm"):
        return DocumentFormat.HTML
    raise ValueError(f"Unsupported file format: {suffix}")


def _parse_document(path: Path, fmt: DocumentFormat) -> tuple[str, str]:
    """Parse and return (full_text, content_hash)."""
    if fmt == DocumentFormat.PDF:
        doc = parse_pdf(path)
        return doc.full_text, doc.content_hash
    else:
        doc_html = parse_html(path)
        return doc_html.full_text, doc_html.content_hash


async def ingest_document(
    path: str | Path,
    *,
    entity_extractor: Any | None = None,
    graph_writer: Any | None = None,
    vector_indexer: Any | None = None,
    neo4j_dedup: Neo4jClient | None = None,
    force: bool = False,
) -> IngestionResult:
    """Run the full ingestion pipeline for a single document.

    Args:
        path: Path to the regulatory document (PDF or HTML).
        entity_extractor: Callable(text, hash) -> ExtractedEntities. If None, extraction is skipped.
        graph_writer: Callable(ExtractedEntities) -> GraphWriteStatus. If None, graph write is skipped.
        vector_indexer: Callable(chunks) -> bool. If None, vector indexing is skipped.
        neo4j_dedup: If set, durable idempotency and progress via ``IngestionRecord`` nodes.
        force: If True, re-ingest even if the content hash was seen before.
    """
    path = Path(path)
    result = IngestionResult(status=IngestionStatus.SUCCESS)

    try:
        fmt = _detect_format(path)
    except ValueError as exc:
        return IngestionResult(status=IngestionStatus.PARSE_ERROR, errors=[str(exc)])

    try:
        full_text, content_hash = _parse_document(path, fmt)
    except Exception as exc:
        logger.error("Parse failed for %s: %s", path, exc)
        return IngestionResult(status=IngestionStatus.PARSE_ERROR, errors=[str(exc)])

    result.document_hash = content_hash

    if neo4j_dedup and not force and content_hash not in _ingested_hashes:
        await _ensure_neo4j_dedup_for_hash(neo4j_dedup, content_hash)

    if not force and content_hash in _ingested_hashes:
        logger.info("Skipping duplicate document: %s (hash=%s)", path.name, content_hash[:12])
        return IngestionResult(status=IngestionStatus.SKIPPED_DUPLICATE, document_hash=content_hash)

    chunks = chunk_text(
        full_text,
        source_hash=content_hash,
        metadata={"source": str(path), "format": fmt.value},
    )
    result.chunks_produced = len(chunks)
    logger.info("Produced %d chunks from %s", len(chunks), path.name)

    if entity_extractor:
        try:
            entities: ExtractedEntities = await entity_extractor(full_text, content_hash)
            result.entities_extracted = True

            if graph_writer:
                try:
                    write_status = await graph_writer(entities)
                    result.graph_written = write_status.success
                    if not write_status.success:
                        result.errors.extend(write_status.errors)
                except Exception as exc:
                    result.errors.append(f"Graph write failed: {exc}")
                    result.status = IngestionStatus.PARTIAL_FAILURE

        except Exception as exc:
            logger.error("Entity extraction failed: %s", exc)
            result.errors.append(f"Extraction failed: {exc}")
            result.status = IngestionStatus.EXTRACTION_ERROR

    if vector_indexer:
        try:
            indexed = await vector_indexer(chunks)
            result.vector_indexed = indexed
        except Exception as exc:
            logger.error("Vector indexing failed: %s", exc)
            result.errors.append(f"Vector indexing failed: {exc}")
            if result.status == IngestionStatus.SUCCESS:
                result.status = IngestionStatus.PARTIAL_FAILURE

    if result.errors and result.status == IngestionStatus.SUCCESS:
        result.status = IngestionStatus.PARTIAL_FAILURE

    if result.status == IngestionStatus.SUCCESS:
        _ingested_hashes.add(content_hash)

    if neo4j_dedup:
        try:
            has_graph = graph_writer is not None
            has_vector = vector_indexer is not None
            graph_ok = result.graph_written if has_graph else True
            vector_ok = result.vector_indexed if has_vector else True
            pipeline_done = result.status == IngestionStatus.SUCCESS
            await upsert_ingestion_progress(
                neo4j_dedup,
                content_hash,
                graph_indexed=graph_ok,
                vector_indexed=vector_ok,
                pipeline_complete=pipeline_done,
            )
        except Exception as exc:
            logger.warning("Failed to persist IngestionRecord for %s: %s", content_hash[:12], exc)

    return result


def reset_ingestion_state() -> None:
    """Clear the in-memory set of ingested hashes (for testing)."""
    _ingested_hashes.clear()
