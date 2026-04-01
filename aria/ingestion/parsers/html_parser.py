"""HTML document parser using BeautifulSoup.

Extracts text from regulatory HTML documents (e.g. EUR-Lex pages),
cleaning boilerplate and preserving structural elements.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

BOILERPLATE_SELECTORS = [
    "nav",
    "footer",
    "header",
    ".cookie-banner",
    "#sidebar",
    "script",
    "style",
    "noscript",
]


@dataclass
class ParsedSection:
    heading: str
    text: str
    level: int = 0


@dataclass
class ParsedHTMLDocument:
    source_path: str
    content_hash: str
    title: str = ""
    sections: list[ParsedSection] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        parts = []
        for s in self.sections:
            if s.heading:
                parts.append(f"{s.heading}\n{s.text}")
            else:
                parts.append(s.text)
        return "\n\n".join(parts)


def _remove_boilerplate(soup: BeautifulSoup) -> None:
    for selector in BOILERPLATE_SELECTORS:
        for tag in soup.select(selector):
            tag.decompose()


def _extract_sections(soup: BeautifulSoup) -> list[ParsedSection]:
    sections: list[ParsedSection] = []
    current_heading = ""
    current_level = 0
    current_text_parts: list[str] = []

    body = soup.body or soup
    for element in body.children:
        if not isinstance(element, Tag):
            text = element.strip() if isinstance(element, str) else ""
            if text:
                current_text_parts.append(text)
            continue

        if element.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            if current_text_parts or current_heading:
                sections.append(
                    ParsedSection(
                        heading=current_heading,
                        text="\n".join(current_text_parts),
                        level=current_level,
                    )
                )
            current_heading = element.get_text(strip=True)
            current_level = int(element.name[1])
            current_text_parts = []
        else:
            text = element.get_text(separator="\n", strip=True)
            if text:
                current_text_parts.append(text)

    if current_text_parts or current_heading:
        sections.append(
            ParsedSection(
                heading=current_heading,
                text="\n".join(current_text_parts),
                level=current_level,
            )
        )

    return sections


def parse_html(source: str | Path, *, is_file: bool = True) -> ParsedHTMLDocument:
    """Parse an HTML document from a file path or raw HTML string.

    Args:
        source: File path or raw HTML string.
        is_file: If True, treat source as a file path.
    """
    if is_file:
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"HTML file not found: {path}")
        raw = path.read_text(encoding="utf-8")
        source_path = str(path)
    else:
        raw = str(source)
        source_path = "<inline>"

    content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    soup = BeautifulSoup(raw, "lxml")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    _remove_boilerplate(soup)
    sections = _extract_sections(soup)

    logger.info(
        "Parsed HTML %s: %d sections, hash=%s",
        source_path, len(sections), content_hash[:12],
    )
    return ParsedHTMLDocument(
        source_path=source_path,
        content_hash=content_hash,
        title=title,
        sections=sections,
    )
