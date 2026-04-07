"""HTTP API size limits (configurable for tests via ``ARIA_MAX_INGEST_BODY_BYTES``)."""

from __future__ import annotations

import os

MAX_INGEST_BODY_BYTES = int(
    os.environ.get("ARIA_MAX_INGEST_BODY_BYTES", str(12 * 1024 * 1024)),
)
