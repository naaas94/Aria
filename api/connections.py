"""Best-effort wiring of Neo4j and Chroma for live API and /ready checks."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from fastapi import Request

from aria.graph.client import Neo4jClient
from aria.protocols.a2a.agent_card import AGENT_CARDS
from aria.protocols.a2a.registry import AgentRegistry
from aria.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class AppConnections:
    neo4j: Neo4jClient | None = None
    vector_store: VectorStore | None = None
    agent_registry: AgentRegistry = field(default_factory=AgentRegistry)
    #: Populated when ``connect_app_dependencies(strict=True)`` records infra connection failures
    #: (distinguishes "unreachable" from "not configured" in CLI status).
    connection_errors: dict[str, str] = field(default_factory=dict)


def get_app_connections(request: Request) -> AppConnections:
    """Return app-scoped connections, initializing a minimal registry if lifespan did not run.

    Ensures ``TestClient`` usage without a context manager still has ``agent_registry``
    populated; full Neo4j/Chroma wiring only happens via ``lifespan``.
    """
    state = request.app.state
    existing: AppConnections | None = getattr(state, "connections", None)
    if existing is not None:
        return existing
    conn = AppConnections()
    for card in AGENT_CARDS.values():
        conn.agent_registry.register(card)
    state.connections = conn
    return conn


async def connect_app_dependencies(*, strict: bool = False) -> AppConnections:
    """Connect optional infrastructure; failures are logged and left as None.

    When ``strict`` is True (e.g. CLI ``status``), connection failures are recorded in
    ``connection_errors`` under ``neo4j`` / ``chroma`` so callers can surface unreachable
    backends instead of only "not configured". Exceptions are still not raised for
    optional infra unless we add a stricter mode later.
    """
    connections = AppConnections()

    for card in AGENT_CARDS.values():
        connections.agent_registry.register(card)

    uri = os.getenv("NEO4J_URI", "").strip()
    if uri:
        try:
            neo = Neo4jClient(
                uri,
                os.getenv("NEO4J_USER", "neo4j"),
                os.getenv("NEO4J_PASSWORD", "aria_dev_password"),
            )
            await neo.connect()
            if await neo.health_check():
                connections.neo4j = neo
            else:
                await neo.close()
                if strict:
                    connections.connection_errors["neo4j"] = "health check failed"
        except Exception as exc:
            if strict:
                connections.connection_errors["neo4j"] = (
                    f"{type(exc).__name__}: {exc}"[:500]
                )
            else:
                logger.exception(
                    "Neo4j connection failed; live graph features unavailable",
                )

    try:
        vs = VectorStore()
        vs.connect()
        connections.vector_store = vs
    except Exception as exc:
        if strict:
            connections.connection_errors["chroma"] = f"{type(exc).__name__}: {exc}"[:500]
        else:
            logger.exception(
                "ChromaDB connection failed; live vector/query features unavailable",
            )

    return connections


async def disconnect_app_dependencies(connections: AppConnections) -> None:
    if connections.neo4j:
        await connections.neo4j.close()
        connections.neo4j = None
