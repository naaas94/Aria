"""GET /impact/{regulation_id} — impact report (placeholder or live)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from api.config import placeholder_api_enabled
from api.connections import get_app_connections
from api.errors import ServiceUnavailableBody
from aria.services.impact_report import (
    ImpactReportUnavailable,
    ImpactSummaryResponse,
    run_impact_report,
)

router = APIRouter(prefix="/impact", tags=["impact"])


@router.get(
    "/{regulation_id}",
    response_model=ImpactSummaryResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ServiceUnavailableBody,
            "description": "Live mode without Neo4j (ARIA_PLACEHOLDER_API=false).",
        },
    },
)
async def get_impact_report(
    regulation_id: str,
    request: Request,
    response: Response,
) -> ImpactSummaryResponse | JSONResponse:
    """Retrieve an impact analysis summary for a regulation.

    With ``ARIA_PLACEHOLDER_API=true`` (default), returns a documented placeholder
    and ``X-ARIA-Mode: placeholder``.

    With ``ARIA_PLACEHOLDER_API=false``, runs :class:`ImpactAnalyzerAgent` against
    Neo4j and returns ``X-ARIA-Mode: live``. If Neo4j is not connected, returns 503.
    """
    conns = get_app_connections(request)
    outcome = await run_impact_report(
        regulation_id,
        conns,
        use_placeholder=placeholder_api_enabled(),
    )
    if isinstance(outcome, ImpactReportUnavailable):
        body = ServiceUnavailableBody(
            detail=outcome.detail,
            missing_dependencies=outcome.missing_dependencies,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=body.model_dump(),
        )

    response.headers["X-ARIA-Mode"] = outcome.aria_mode
    return outcome.response
