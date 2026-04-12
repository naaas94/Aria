"""Initialize Neo4j graph schema (constraints + indexes)."""

from __future__ import annotations

import asyncio
import os
import sys

import typer

from aria.graph.client import Neo4jClient


async def _run_init() -> None:
    uri = os.getenv("NEO4J_URI", "").strip()
    if not uri:
        print("error: NEO4J_URI is not set or empty", file=sys.stderr)
        raise typer.Exit(1)
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "aria_dev_password")
    client = Neo4jClient(uri, user, password)
    try:
        await client.connect()
        await client.initialize_schema()
    except Exception as exc:
        print(f"error: Neo4j init failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise typer.Exit(1) from exc
    finally:
        await client.close()


def init_schema() -> None:
    """Connect to Neo4j and apply graph schema (constraints and indexes)."""
    asyncio.run(_run_init())
