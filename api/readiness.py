"""Dependency readiness probes for Kubernetes-style /ready checks."""

from __future__ import annotations

import os
from typing import Any

from fastapi import Request

from api.connections import get_app_connections
from aria.health import LlmReadyProbeCache, assess_app_connections


def _llm_probe_cache_for_app(request: Request) -> LlmReadyProbeCache:
    """One cache per app instance; TTL from ``ARIA_READY_LLM_CACHE_TTL_SECONDS`` (default 300)."""
    cache = getattr(request.app.state, "_llm_ready_probe_cache", None)
    if cache is None:
        ttl = float(os.getenv("ARIA_READY_LLM_CACHE_TTL_SECONDS", "300"))
        cache = LlmReadyProbeCache(ttl)
        request.app.state._llm_ready_probe_cache = cache
    return cache


async def readiness_payload(request: Request) -> dict[str, Any]:
    """Probe dependencies using pooled ``app.state.connections`` (no per-request clients)."""
    conns = get_app_connections(request)
    cache = _llm_probe_cache_for_app(request)
    report = await assess_app_connections(conns, llm_probe=cache.probe)
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
