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


async def connect_app_dependencies() -> AppConnections:
    """Connect optional infrastructure; failures are logged and left as None."""
    connections = AppConnections()

    for card in AGENT_CARDS.values():
        connections.agent_registry.register(card)

    uri = os.getenv("NEO4J_URI", "").strip()
    if uri:
        try:
            neo = Neo4jClient(
                uri,
                os.getenv("NEO4J_USER", "neo4j"),
                os.getenv("NEO4J_PASSWORD", ""),
            )
            await neo.connect()
            if await neo.health_check():
                connections.neo4j = neo
            else:
                await neo.close()
        except Exception:
            logger.exception("Neo4j connection failed; live graph features unavailable")

    try:
        vs = VectorStore()
        vs.connect()
        connections.vector_store = vs
    except Exception:
        logger.exception("ChromaDB connection failed; live vector/query features unavailable")

    return connections


async def disconnect_app_dependencies(connections: AppConnections) -> None:
    if connections.neo4j:
        await connections.neo4j.close()
        connections.neo4j = None
