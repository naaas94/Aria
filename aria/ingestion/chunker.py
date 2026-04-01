"""Semantic chunking strategy for regulatory documents.

Splits parsed documents into overlapping chunks suitable for embedding
and vector storage, preserving structural context (article boundaries,
section headings).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field


@dataclass
class DocumentChunk:
    chunk_id: str
    text: str
    source_document_hash: str
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def token_estimate(self) -> int:
        return len(self.text.split())


DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 100
MIN_CHUNK_SIZE = 50


def _generate_chunk_id(doc_hash: str, index: int) -> str:
    raw = f"{doc_hash}:{index}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _split_into_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def chunk_text(
    text: str,
    *,
    source_hash: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    metadata: dict[str, str] | None = None,
) -> list[DocumentChunk]:
    """Split text into overlapping chunks by word count, respecting sentence boundaries."""

    sentences = _split_into_sentences(text)
    if not sentences:
        return []

    chunks: list[DocumentChunk] = []
    current_words: list[str] = []
    current_sentences: list[str] = []
    chunk_index = 0

    for sentence in sentences:
        words = sentence.split()
        if len(current_words) + len(words) > chunk_size and len(current_words) >= MIN_CHUNK_SIZE:
            chunk_text_str = " ".join(current_sentences)
            chunks.append(
                DocumentChunk(
                    chunk_id=_generate_chunk_id(source_hash, chunk_index),
                    text=chunk_text_str,
                    source_document_hash=source_hash,
                    metadata=metadata or {},
                )
            )
            chunk_index += 1

            overlap_words = 0
            overlap_start = len(current_sentences)
            for i in range(len(current_sentences) - 1, -1, -1):
                overlap_words += len(current_sentences[i].split())
                if overlap_words >= chunk_overlap:
                    overlap_start = i
                    break
            current_sentences = current_sentences[overlap_start:]
            current_words = []
            for s in current_sentences:
                current_words.extend(s.split())

        current_sentences.append(sentence)
        current_words.extend(words)

    if current_sentences:
        chunk_text_str = " ".join(current_sentences)
        if len(chunk_text_str.split()) >= MIN_CHUNK_SIZE or not chunks:
            chunks.append(
                DocumentChunk(
                    chunk_id=_generate_chunk_id(source_hash, chunk_index),
                    text=chunk_text_str,
                    source_document_hash=source_hash,
                    metadata=metadata or {},
                )
            )

    return chunks
