"""Dependency readiness probes for Kubernetes-style /ready checks."""

from __future__ import annotations

from typing import Any

from fastapi import Request

from api.connections import get_app_connections
from aria.health import assess_app_connections


async def readiness_payload(request: Request) -> dict[str, Any]:
    """Probe dependencies using pooled ``app.state.connections`` (no per-request clients)."""
    conns = get_app_connections(request)
    report = await assess_app_connections(conns)
    # Data plane gates HTTP status; LLM is informational (see ``aria.health.assessment`` docstring).
    if report.neo4j_ok and report.chroma_ok:
        status = "ready"
        code = 200
    else:
        status = "degraded"
        code = 503
    body: dict[str, Any] = {
        "status": status,
        "service": "aria-api",
        "neo4j": report.neo4j_ok,
        "chroma": report.chroma_ok,
        "llm": report.llm_ok,
    }
    if report.errors:
        body["errors"] = report.errors
    return {"body": body, "status_code": code}
