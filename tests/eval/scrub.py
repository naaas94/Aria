"""Best-effort redaction of secrets and PII-like patterns in eval payloads."""

from __future__ import annotations

import re
from typing import Any

_SCRUB_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*\S+"),
    re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
]


def scrub_str(text: str) -> str:
    """Remove secrets and PII-like patterns from a string."""
    for pat in _SCRUB_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


def scrub_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Deep-copy a dict structure with string values scrubbed."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, str):
            out[k] = scrub_str(v)
        elif isinstance(v, dict):
            out[k] = scrub_dict(v)
        elif isinstance(v, list):
            out[k] = [
                scrub_dict(i) if isinstance(i, dict) else (scrub_str(i) if isinstance(i, str) else i)
                for i in v
            ]
        else:
            out[k] = v
    return out
