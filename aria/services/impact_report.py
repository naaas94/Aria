"""Impact report for a regulation (placeholder or live Neo4j analysis)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from aria.agents.impact_analyzer import ImpactAnalyzerAgent
from aria.contracts.impact import ImpactReport
from aria.graph.client import Neo4jClient
from aria.graph.queries import execute_named_query


class ImpactReportConnections(Protocol):
    """Minimal connection shape for :func:`run_impact_report` (e.g. ``AppConnections``)."""

    neo4j: Neo4jClient | None


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


@dataclass(frozen=True)
class ImpactReportSuccess:
    response: ImpactSummaryResponse
    aria_mode: Literal["placeholder", "live"]


@dataclass(frozen=True)
class ImpactReportUnavailable:
    detail: str
    missing_dependencies: list[str]


ImpactReportOutcome = ImpactReportSuccess | ImpactReportUnavailable


async def run_impact_report(
    regulation_id: str,
    conns: ImpactReportConnections,
    *,
    use_placeholder: bool,
) -> ImpactReportOutcome:
    """Build an impact analysis summary for ``regulation_id``.

    When ``use_placeholder`` is true, returns synthetic content. Otherwise requires Neo4j.
    """
    if use_placeholder:
        return ImpactReportSuccess(
            response=ImpactSummaryResponse(
                regulation_id=regulation_id,
                regulation_title=f"[Placeholder] Regulation {regulation_id}",
                total_requirements=0,
                affected_systems=0,
                gap_count=0,
                risk_level="unknown",
                details=[],
            ),
            aria_mode="placeholder",
        )

    neo = conns.neo4j
    if neo is None:
        return ImpactReportUnavailable(
            detail="Live impact analysis requires a connected Neo4j instance.",
            missing_dependencies=["neo4j"],
        )

    async def graph_query(name: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        cypher, p = execute_named_query(name, params)
        return await neo.execute_read(cypher, p)

    agent = ImpactAnalyzerAgent(graph_query_fn=graph_query)
    raw = await agent.process({"regulation_id": regulation_id})
    report = ImpactReport.model_validate(raw)
    return ImpactReportSuccess(
        response=_impact_report_to_summary(report),
        aria_mode="live",
    )
