"""POST /query — multi-hop compliance query (placeholder or live)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from api.config import placeholder_api_enabled
from api.connections import get_app_connections
from api.errors import ServiceUnavailableBody
from aria.services.compliance_query import (
    ComplianceQueryRequest,
    ComplianceQueryResponse,
    ComplianceQueryUnavailable,
    run_compliance_query,
)

router = APIRouter(prefix="/query", tags=["query"])


@router.post(
    "",
    response_model=ComplianceQueryResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ServiceUnavailableBody,
            "description": "Live mode without required Neo4j/Chroma (ARIA_PLACEHOLDER_API=false).",
        },
    },
)
async def compliance_query(
    query_request: ComplianceQueryRequest,
    request: Request,
    response: Response,
) -> ComplianceQueryResponse | JSONResponse:
    """Answer a compliance question using GraphRAG or vector-only retrieval.

    With ``ARIA_PLACEHOLDER_API=true`` (default), returns a documented placeholder
    and ``X-ARIA-Mode: placeholder``.

    With ``ARIA_PLACEHOLDER_API=false``, runs hybrid or vector retrieval plus an LLM.
    Requires Chroma for all live paths; GraphRAG also requires Neo4j.
    """
    conns = get_app_connections(request)
    outcome = await run_compliance_query(
        query_request,
        conns,
        use_placeholder=placeholder_api_enabled(),
    )
    if isinstance(outcome, ComplianceQueryUnavailable):
        svc = ServiceUnavailableBody(
            detail=outcome.detail,
            missing_dependencies=outcome.missing_dependencies,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=svc.model_dump(),
        )

    response.headers["X-ARIA-Mode"] = outcome.aria_mode
    return outcome.response
