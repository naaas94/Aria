"""HTTP API size limits (configurable for tests via ``ARIA_MAX_INGEST_BODY_BYTES``)."""

from __future__ import annotations

import os

# Default used when env vars are unset — keep in sync with ``INGEST_MAX_BYTES`` default in
# ``api.routers.ingest`` (router application limit) and ``LimitIngestBodySizeMiddleware``
# (``Content-Length`` pre-check for ``POST /ingest*``).
DEFAULT_INGEST_MAX_BYTES = 12 * 1024 * 1024

MAX_INGEST_BODY_BYTES = int(
    os.environ.get("ARIA_MAX_INGEST_BODY_BYTES", str(DEFAULT_INGEST_MAX_BYTES)),
)
