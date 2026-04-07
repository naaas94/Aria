"""FastAPI application — ARIA REST interface."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.config import cors_allow_origins, is_production_deployment
from api.deps import _configured_api_key, require_api_key_when_configured
from api.middleware_body_limit import LimitIngestBodySizeMiddleware
from api.connections import (
    AppConnections,
    connect_app_dependencies,
    disconnect_app_dependencies,
    get_app_connections,
)
from api.errors import ErrorBody, validation_error_payload
from api.readiness import readiness_payload
from api.routers import agents, impact, ingest, query

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not _configured_api_key():
        logger.warning(
            "API_KEY / ARIA_API_KEY is not set — authenticated routes are open. "
            "Set API_KEY (or ARIA_API_KEY) for any network-exposed deployment.",
        )
    connections = await connect_app_dependencies()
    app.state.connections = connections
    try:
        yield
    finally:
        await disconnect_app_dependencies(connections)


def _build_fastapi() -> FastAPI:
    kwargs: dict = {
        "title": "ARIA — Automated Regulatory Impact Agent",
        "description": (
            "GraphRAG-powered multi-agent system for regulatory compliance analysis. "
            "Ingests regulatory documents, builds a Neo4j knowledge graph, answers "
            "multi-hop compliance queries, and routes remediation tasks.\n\n"
            "When `ARIA_PLACEHOLDER_API=true` (default), `GET /impact` and `POST /query` "
            "return synthetic data with the `X-ARIA-Mode: placeholder` header. "
            "Set `ARIA_PLACEHOLDER_API=false` to require live Neo4j/Chroma (and LLM for query)."
        ),
        "version": "0.1.0",
        "lifespan": lifespan,
    }
    if is_production_deployment():
        kwargs["docs_url"] = None
        kwargs["redoc_url"] = None
        kwargs["openapi_url"] = None
    return FastAPI(**kwargs)


app = _build_fastapi()

_origins = cors_allow_origins()
if _origins:
    # Browsers forbid credentials with wildcard origins.
    allow_creds = "*" not in _origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=allow_creds,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_middleware(LimitIngestBodySizeMiddleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code_map = {
        status.HTTP_400_BAD_REQUEST: "bad_request",
        status.HTTP_404_NOT_FOUND: "not_found",
        status.HTTP_503_SERVICE_UNAVAILABLE: "service_unavailable",
        status.HTTP_401_UNAUTHORIZED: "unauthorized",
    }
    code = code_map.get(exc.status_code, "http_error")
    hdrs = dict(exc.headers) if exc.headers else None
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": code},
        headers=hdrs,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=validation_error_payload(exc.errors()),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, HTTPException):
        return await http_exception_handler(request, exc)
    if isinstance(exc, RequestValidationError):
        return await request_validation_handler(request, exc)
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    body = ErrorBody(detail="An unexpected error occurred.", code="internal_error")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=body.model_dump(),
    )


_route_auth = [Depends(require_api_key_when_configured)]

app.include_router(ingest.router, dependencies=_route_auth)
app.include_router(query.router, dependencies=_route_auth)
app.include_router(impact.router, dependencies=_route_auth)
app.include_router(agents.router, dependencies=_route_auth)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness: process is running (no dependency checks)."""
    return {"status": "healthy", "service": "aria-api"}


@app.get("/ready")
async def ready_check() -> JSONResponse:
    """Readiness: Neo4j Bolt + Chroma heartbeat (env-based; does not require app.state)."""
    payload = await readiness_payload()
    return JSONResponse(
        status_code=payload["status_code"],
        content=payload["body"],
    )
