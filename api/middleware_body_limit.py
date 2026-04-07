"""Reject oversized POST bodies to ``/ingest`` routes before the app reads them."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from api import limits


class LimitIngestBodySizeMiddleware(BaseHTTPMiddleware):
    """Return 413 when ``Content-Length`` exceeds ``limits.MAX_INGEST_BODY_BYTES``."""

    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path.startswith("/ingest"):
            cl = request.headers.get("content-length")
            if cl is not None:
                try:
                    n = int(cl)
                except ValueError:
                    pass
                else:
                    max_b = limits.MAX_INGEST_BODY_BYTES
                    if n > max_b:
                        return JSONResponse(
                            status_code=413,
                            content={
                                "detail": (
                                    f"Request body exceeds maximum of {max_b} bytes"
                                ),
                            },
                        )
        return await call_next(request)
