"""FastAPI application — ARIA REST interface."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import agents, impact, ingest, query

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

app = FastAPI(
    title="ARIA — Automated Regulatory Impact Agent",
    description=(
        "GraphRAG-powered multi-agent system for regulatory compliance analysis. "
        "Ingests regulatory documents, builds a Neo4j knowledge graph, answers "
        "multi-hop compliance queries, and routes remediation tasks."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(impact.router)
app.include_router(agents.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "aria-api"}
