"""Single source of truth for the public HTTP OpenAPI path set (no methods)."""

from __future__ import annotations

# Keep in sync with FastAPI ``app.openapi()`` paths; update when routes change.
EXPECTED_OPENAPI_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/ready",
        "/metrics",
        "/telemetry",
        "/ingest/text",
        "/ingest/file",
        "/query",
        "/impact/{regulation_id}",
        "/agents",
        "/agents/{agent_name}",
    }
)
