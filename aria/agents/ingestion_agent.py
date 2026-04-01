"""Ingestion agent — triggers and monitors the ingestion pipeline.

Receives raw document content, delegates to parsers and the entity
extractor, validates output, and reports status to the supervisor.
"""

from __future__ import annotations

import hashlib
from typing import Any

from aria.agents.base import BaseAgent
from aria.ingestion.chunker import chunk_text


class IngestionAgent(BaseAgent):
    name = "ingestion_agent"

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        raw_document = input_data.get("raw_document", "")
        if not raw_document:
            raise ValueError("No raw_document provided to ingestion agent")

        content_hash = hashlib.sha256(raw_document.encode("utf-8")).hexdigest()

        chunks = chunk_text(
            raw_document,
            source_hash=content_hash,
            metadata={"source": input_data.get("source", "api")},
        )

        self.logger.info(
            "Ingestion complete: hash=%s, chunks=%d",
            content_hash[:12], len(chunks),
        )

        return {
            "content_hash": content_hash,
            "chunk_count": len(chunks),
            "chunks": [
                {"chunk_id": c.chunk_id, "text": c.text, "metadata": c.metadata}
                for c in chunks
            ],
        }
