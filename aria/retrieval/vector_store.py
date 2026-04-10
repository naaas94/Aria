"""ChromaDB interface for vector storage and semantic search.

Manages document chunk embeddings and provides similarity search
for the retrieval pipeline.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import chromadb
from chromadb.config import Settings

from aria.ingestion.chunker import DocumentChunk

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = "aria_regulatory_chunks"


class VectorStore:
    """Async-compatible wrapper around ChromaDB for regulatory document chunks."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> None:
        self._host = host or os.getenv("CHROMA_HOST", "localhost")
        self._port = port or int(os.getenv("CHROMA_PORT", "8000"))
        self._collection_name = collection_name
        self._client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None

    def connect(self) -> None:
        self._client = chromadb.HttpClient(
            host=self._host,
            port=self._port,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "Connected to ChromaDB at %s:%d, collection=%s",
            self._host, self._port, self._collection_name,
        )

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            raise RuntimeError("VectorStore not connected — call connect() first")
        return self._collection

    def index_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Add or update chunks in the vector store. Returns count indexed."""
        if not chunks:
            return 0

        self.collection.upsert(
            ids=[c.chunk_id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[
                {
                    "source_hash": c.source_document_hash,
                    **c.metadata,
                }
                for c in chunks
            ],
        )
        logger.info("Indexed %d chunks into %s", len(chunks), self._collection_name)
        return len(chunks)

    def search(
        self,
        query_text: str,
        top_k: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Semantic search over indexed chunks."""
        kwargs: dict[str, Any] = {
            "query_texts": [query_text],
            "n_results": top_k,
        }
        if where:
            kwargs["where"] = where

        results = self.collection.query(**kwargs)

        retrieved: list[RetrievedChunk] = []
        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                retrieved.append(
                    RetrievedChunk(
                        chunk_id=chunk_id,
                        text=results["documents"][0][i] if results["documents"] else "",
                        score=1.0 - (results["distances"][0][i] if results["distances"] else 0.0),
                        metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                    )
                )

        return retrieved

    def delete_by_source_hash(self, source_hash: str) -> None:
        """Remove all chunks associated with a source document hash."""
        self.collection.delete(where={"source_hash": source_hash})

    def count(self) -> int:
        return self.collection.count()

    def health_check(self) -> bool:
        """Lightweight probe using the existing Chroma HTTP client (no new connections)."""
        if self._client is None:
            return False
        try:
            self._client.heartbeat()
            return True
        except Exception:
            logger.debug("Chroma health check failed", exc_info=True)
            return False


class RetrievedChunk:
    """A single chunk returned from vector search with its similarity score."""

    __slots__ = ("chunk_id", "text", "score", "metadata")

    def __init__(
        self,
        chunk_id: str,
        text: str,
        score: float,
        metadata: dict[str, Any],
    ) -> None:
        self.chunk_id = chunk_id
        self.text = text
        self.score = score
        self.metadata = metadata

    def __repr__(self) -> str:
        return f"RetrievedChunk(id={self.chunk_id!r}, score={self.score:.3f})"
