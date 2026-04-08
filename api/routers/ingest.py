"""POST /ingest — trigger document ingestion."""

from __future__ import annotations

import hashlib
import os

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from aria.ingestion.chunker import chunk_text

router = APIRouter(prefix="/ingest", tags=["ingestion"])

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

    text: str = Field(..., description="Raw regulatory document text")
    source: str = Field(default="api", description="Source identifier")


class IngestResponse(BaseModel):
    status: str
    document_hash: str
    chunks_produced: int
    message: str = ""


@router.post("/text", response_model=IngestResponse)
async def ingest_text(request: IngestTextRequest) -> IngestResponse:
    """Ingest a regulatory document from raw text."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Empty document text")

    content_hash = hashlib.sha256(request.text.encode("utf-8")).hexdigest()
    chunks = chunk_text(
        request.text,
        source_hash=content_hash,
        metadata={"source": request.source},
    )

    return IngestResponse(
        status="success",
        document_hash=content_hash,
        chunks_produced=len(chunks),
        message=f"Ingested {len(chunks)} chunks from text input",
    )


@router.post("/file", response_model=IngestResponse)
async def ingest_file(file: UploadFile = File(...)) -> IngestResponse:
    """Ingest a regulatory document from an uploaded file."""
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

    chunks = chunk_text(
        text,
        source_hash=content_hash,
        metadata={"source": file.filename},
    )

    return IngestResponse(
        status="success",
        document_hash=content_hash,
        chunks_produced=len(chunks),
        message=f"Ingested {len(chunks)} chunks from {file.filename}",
    )
