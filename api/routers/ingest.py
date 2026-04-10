"""POST /ingest — HTTP chunking smoke path (not the full ingestion pipeline).

These routes validate request sizing, compute a content hash, run in-memory semantic
chunking, and record metrics. They do **not** persist chunks, call ``ingest_document``,
write Neo4j, or index Chroma. For loading documents into the knowledge base, see the
README section **How to load documents (developer / offline)**.
"""

from __future__ import annotations

import hashlib
import os
import time

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from aria.ingestion.chunker import chunk_text
from aria.observability.metrics import INGESTION_COUNTER, INGESTION_DURATION

router = APIRouter(
    prefix="/ingest",
    tags=["ingestion"],
)

_DEFAULT_MAX_BYTES = 10 * 1024 * 1024


def _ingest_max_bytes() -> int:
    return int(os.getenv("INGEST_MAX_BYTES", str(_DEFAULT_MAX_BYTES)))


def _upload_content_type_allowed(content_type: str | None) -> bool:
    """Allow ``text/*``, ``application/octet-stream``, or missing type (client default)."""
    if content_type is None or not content_type.strip():
        return True
    main = content_type.split(";")[0].strip().lower()
    if main == "application/octet-stream":
        return True
    return main.startswith("text/")


class IngestTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(
        ...,
        description=(
            "Raw document text to chunk in memory. This does not run the full "
            "ingestion pipeline (no graph or vector store writes)."
        ),
    )
    source: str = Field(
        default="api",
        description="Label stored in chunk metadata for debugging (not persisted server-side).",
    )


class IngestResponse(BaseModel):
    status: str = Field(
        ...,
        description="Always ``success`` when chunking completed without error.",
    )
    document_hash: str = Field(
        ...,
        description="SHA-256 (hex) of the raw body bytes or UTF-8 text.",
    )
    chunks_produced: int = Field(
        ...,
        description="Number of in-memory chunks produced; chunks are not returned or stored.",
    )
    message: str = Field(
        default="",
        description="Human-readable summary for operators.",
    )


@router.post(
    "/text",
    response_model=IngestResponse,
    summary="Chunk JSON text (smoke / metrics)",
    description=(
        "Runs **in-memory chunking only**: hashes the body, splits into semantic chunks, "
        "increments Prometheus ingestion metrics. Does **not** invoke "
        "``aria.ingestion.pipeline.ingest_document``, entity extraction, Neo4j, or Chroma. "
        "Use offline/developer flows to load documents into the knowledge base."
    ),
)
async def ingest_text(request: IngestTextRequest) -> IngestResponse:
    """Chunk raw text from JSON (see route description)."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Empty document text")

    content_hash = hashlib.sha256(request.text.encode("utf-8")).hexdigest()
    start = time.monotonic()
    try:
        chunks = chunk_text(
            request.text,
            source_hash=content_hash,
            metadata={"source": request.source},
        )
        INGESTION_COUNTER.labels(status="success").inc()
        INGESTION_DURATION.labels(format="text").observe(time.monotonic() - start)
    except Exception:
        INGESTION_COUNTER.labels(status="error").inc()
        raise

    return IngestResponse(
        status="success",
        document_hash=content_hash,
        chunks_produced=len(chunks),
        message=f"Ingested {len(chunks)} chunks from text input",
    )


@router.post(
    "/file",
    response_model=IngestResponse,
    summary="Chunk uploaded file (smoke / metrics)",
    description=(
        "Same behavior as ``POST /ingest/text`` but reads the request body from multipart "
        "upload. Decodes bytes as UTF-8 (replacement on errors), then chunks in memory. "
        "Does **not** persist to Neo4j or Chroma or run the full ingestion pipeline."
    ),
)
async def ingest_file(file: UploadFile = File(...)) -> IngestResponse:
    """Chunk an uploaded file (see route description)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if not _upload_content_type_allowed(file.content_type):
        raise HTTPException(
            status_code=415,
            detail="Unsupported Content-Type; use text/* or application/octet-stream",
        )

    content = await file.read()
    if len(content) > _ingest_max_bytes():
        raise HTTPException(status_code=413, detail="Upload exceeds INGEST_MAX_BYTES")
    text = content.decode("utf-8", errors="replace")
    content_hash = hashlib.sha256(content).hexdigest()

    start = time.monotonic()
    try:
        chunks = chunk_text(
            text,
            source_hash=content_hash,
            metadata={"source": file.filename},
        )
        INGESTION_COUNTER.labels(status="success").inc()
        INGESTION_DURATION.labels(format="file").observe(time.monotonic() - start)
    except Exception:
        INGESTION_COUNTER.labels(status="error").inc()
        raise

    return IngestResponse(
        status="success",
        document_hash=content_hash,
        chunks_produced=len(chunks),
        message=f"Ingested {len(chunks)} chunks from {file.filename}",
    )
