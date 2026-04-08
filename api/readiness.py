"""Dependency readiness probes for Kubernetes-style /ready checks."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from aria.graph.client import Neo4jClient

logger = logging.getLogger(__name__)


async def check_neo4j() -> bool:
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "aria_dev_password")
    client = Neo4jClient(uri, user, password)
    try:
        await client.connect()
        return await client.health_check()
    except Exception:
        logger.debug("Neo4j readiness check failed", exc_info=True)
        return False
    finally:
        await client.close()


async def check_chroma() -> bool:
    host = os.getenv("CHROMA_HOST", "localhost")
    port = int(os.getenv("CHROMA_PORT", "8000"))
    url = f"http://{host}:{port}/api/v1/heartbeat"
    try:
        async with httpx.AsyncClient(timeout=3.0) as ac:
            response = await ac.get(url)
            return response.status_code == 200
    except Exception:
        logger.debug("Chroma readiness check failed", exc_info=True)
        return False


async def readiness_payload() -> dict[str, Any]:
    neo4j_ok = await check_neo4j()
    chroma_ok = await check_chroma()
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
