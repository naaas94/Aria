"""Record HTTP request telemetry (method, path, status, latency) per request."""

from __future__ import annotations

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from aria.observability.metrics import HTTP_REQUEST_COUNTER
from aria.observability.telemetry_store import get_telemetry_store

_SKIP_PATHS = frozenset({"/health", "/ready", "/metrics", "/telemetry"})


def _should_skip_path(path: str) -> bool:
    return path in _SKIP_PATHS


class TelemetryMiddleware(BaseHTTPMiddleware):
    """Persist each request to the telemetry store; optional Prometheus counter."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.monotonic()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            latency_ms = (time.monotonic() - start) * 1000.0
            path = request.url.path
            if not _should_skip_path(path):
                ctx = structlog.contextvars.get_contextvars()
                request_id = str(ctx.get("request_id") or "")
                try:
                    get_telemetry_store().record_request(
                        request_id=request_id,
                        method=request.method,
                        path=path,
                        status_code=status_code,
                        latency_ms=latency_ms,
                    )
                    HTTP_REQUEST_COUNTER.labels(
                        method=request.method,
                        status_code=str(status_code),
                    ).inc()
                except Exception:
                    pass
