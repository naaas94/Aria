"""GET /impact/{regulation_id} — impact report (placeholder or live)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.config import placeholder_api_enabled
from api.connections import get_app_connections
from api.errors import ServiceUnavailableBody
from aria.agents.impact_analyzer import ImpactAnalyzerAgent
from aria.contracts.impact import ImpactReport
from aria.graph.queries import execute_named_query

router = APIRouter(prefix="/impact", tags=["impact"])


class ImpactSummaryResponse(BaseModel):
    regulation_id: str
    regulation_title: str = ""
    total_requirements: int = 0
    affected_systems: int = 0
    gap_count: int = 0
    risk_level: str = "unknown"
    details: list[dict[str, Any]] = Field(default_factory=list)


def _impact_report_to_summary(report: ImpactReport) -> ImpactSummaryResponse:
    details = [a.model_dump(mode="json") for a in report.affected_systems[:100]]
    return ImpactSummaryResponse(
        regulation_id=report.regulation_id,
        regulation_title=report.regulation_title,
        total_requirements=report.total_requirements,
        affected_systems=len(report.affected_systems),
        gap_count=report.gap_count,
        risk_level=report.risk_level.value,
        details=details,
    )


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

    if placeholder_api_enabled():
        response.headers["X-ARIA-Mode"] = "placeholder"
        return ImpactSummaryResponse(
            regulation_id=regulation_id,
            regulation_title=f"[Placeholder] Regulation {regulation_id}",
            total_requirements=0,
            affected_systems=0,
            gap_count=0,
            risk_level="unknown",
            details=[],
        )

    if conns.neo4j is None:
        body = ServiceUnavailableBody(
            detail="Live impact analysis requires a connected Neo4j instance.",
            missing_dependencies=["neo4j"],
        )
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=body.model_dump())

    response.headers["X-ARIA-Mode"] = "live"

    async def graph_query(name: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        cypher, p = execute_named_query(name, params)
        return await conns.neo4j.execute_read(cypher, p)

    agent = ImpactAnalyzerAgent(graph_query_fn=graph_query)
    raw = await agent.process({"regulation_id": regulation_id})
    report = ImpactReport.model_validate(raw)
    return _impact_report_to_summary(report)
