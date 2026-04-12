"""Framework-agnostic dependency checks for readiness surfaces (/ready, CLI status, preflight).

Kubernetes-style /ready policy (HTTP layer in ``api.readiness``):
- **HTTP status** (200 vs 503) reflects the **data plane** only: Neo4j + Chroma must both pass.
- **LLM** is always reported in JSON as ``llm`` (bool) plus optional per-component messages in
  ``errors``; an unreachable LLM does **not** flip 503, so ingest/query paths that need the graph
  and vector store can still go "ready" while LLM-dependent features may fail at runtime.
  Frequent probes can incur provider cost or rate limits; avoid aggressive /ready polling.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Protocol

import litellm

from aria.graph.client import Neo4jClient
from aria.llm.client import _require_non_placeholder_api_key
from aria.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)

litellm.drop_params = True

_LLM_PROBE_TIMEOUT_S = 12.0
_LLM_PROBE_MAX_TOKENS = 1


@dataclass
class DependencyReport:
    """Result of Neo4j, Chroma, and LLM reachability checks."""

    neo4j_ok: bool
    chroma_ok: bool
    llm_ok: bool
    errors: dict[str, str] = field(default_factory=dict)


class DependencyConnections(Protocol):
    """Minimal shape of :class:`api.connections.AppConnections` for assessment."""

    neo4j: Neo4jClient | None
    vector_store: VectorStore | None


async def probe_llm_reachable() -> tuple[bool, str | None]:
    """One minimal LiteLLM chat call using production env (no LLMClient telemetry/metrics).

    Uses ``LLM_MODEL``, ``LLM_BASE_URL``, ``LLM_API_KEY`` like :class:`aria.llm.client.LLMClient`.
    """
    model = os.getenv("LLM_MODEL", "ollama/llama3.2")
    base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434")
    api_key = os.getenv("LLM_API_KEY", "not-needed")
    try:
        _require_non_placeholder_api_key(model, base_url, api_key)
    except ValueError as exc:
        return False, str(exc)
    try:
        await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": "."}],
            api_base=base_url,
            api_key=api_key,
            temperature=0.0,
            max_tokens=_LLM_PROBE_MAX_TOKENS,
            timeout=_LLM_PROBE_TIMEOUT_S,
        )
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
        logger.debug("LLM readiness probe failed: %s", msg, exc_info=True)
        return False, msg[:500]
    return True, None


async def assess_app_connections(conns: DependencyConnections) -> DependencyReport:
    """Check Neo4j (async), Chroma (sync heartbeat), and LLM (async probe)."""
    errors: dict[str, str] = {}

    if conns.neo4j is None:
        neo4j_ok = False
        errors["neo4j"] = "not configured"
    else:
        try:
            neo4j_ok = await conns.neo4j.health_check()
            if not neo4j_ok:
                errors["neo4j"] = "unhealthy"
        except Exception as exc:
            neo4j_ok = False
            errors["neo4j"] = f"{type(exc).__name__}: {exc}"[:500]
            logger.debug("Neo4j readiness check raised", exc_info=True)

    if conns.vector_store is None:
        chroma_ok = False
        errors["chroma"] = "not configured"
    else:
        try:
            chroma_ok = conns.vector_store.health_check()
            if not chroma_ok:
                errors["chroma"] = "unhealthy"
        except Exception as exc:
            chroma_ok = False
            errors["chroma"] = f"{type(exc).__name__}: {exc}"[:500]
            logger.debug("Chroma readiness check raised", exc_info=True)

    llm_ok, llm_err = await probe_llm_reachable()
    if not llm_ok:
        errors["llm"] = llm_err or "unreachable"

    return DependencyReport(
        neo4j_ok=neo4j_ok,
        chroma_ok=chroma_ok,
        llm_ok=llm_ok,
        errors=errors,
    )
