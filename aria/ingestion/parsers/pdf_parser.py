"""PDF document parser using pdfplumber.

Extracts text content from regulatory PDF documents, preserving page
boundaries and structural hints (headers, lists) where possible.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)


@dataclass
class ParsedPage:
    page_number: int
    text: str


@dataclass
class ParsedDocument:
    source_path: str
    content_hash: str
    pages: list[ParsedPage] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def page_count(self) -> int:
        return len(self.pages)


def parse_pdf(path: str | Path) -> ParsedDocument:
    """Extract text from a PDF file.

    Returns a ParsedDocument with per-page text and a content hash
    suitable for idempotency checks.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    raw_bytes = path.read_bytes()
    content_hash = hashlib.sha256(raw_bytes).hexdigest()

    pages: list[ParsedPage] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append(ParsedPage(page_number=i, text=text.strip()))

    logger.info("Parsed PDF %s: %d pages, hash=%s", path.name, len(pages), content_hash[:12])
    return ParsedDocument(source_path=str(path), content_hash=content_hash, pages=pages)
