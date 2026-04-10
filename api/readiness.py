"""Dependency readiness probes for Kubernetes-style /ready checks."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request

from api.connections import get_app_connections

logger = logging.getLogger(__name__)


async def readiness_payload(request: Request) -> dict[str, Any]:
    """Probe dependencies using pooled ``app.state.connections`` (no per-request clients)."""
    conns = get_app_connections(request)
    neo4j_ok = False
    chroma_ok = False
    if conns.neo4j is not None:
        neo4j_ok = await conns.neo4j.health_check()
    if conns.vector_store is not None:
        chroma_ok = conns.vector_store.health_check()
    if neo4j_ok and chroma_ok:
        status = "ready"
        code = 200
    else:
        status = "degraded"
        code = 503
    return {
        "body": {
            "status": status,
            "service": "aria-api",
            "neo4j": neo4j_ok,
            "chroma": chroma_ok,
        },
        "status_code": code,
    }
