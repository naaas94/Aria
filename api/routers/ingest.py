"""POST /ingest — trigger document ingestion."""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from aria.ingestion.chunker import chunk_text

router = APIRouter(prefix="/ingest", tags=["ingestion"])


class IngestTextRequest(BaseModel):
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

    content = await file.read()
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
