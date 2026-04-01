"""GET /impact/{regulation_id} — impact report."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from aria.contracts.impact import CoverageStatus, RiskLevel

router = APIRouter(prefix="/impact", tags=["impact"])


class ImpactSummaryResponse(BaseModel):
    regulation_id: str
    regulation_title: str = ""
    total_requirements: int = 0
    affected_systems: int = 0
    gap_count: int = 0
    risk_level: str = "unknown"
    details: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/{regulation_id}", response_model=ImpactSummaryResponse)
async def get_impact_report(regulation_id: str) -> ImpactSummaryResponse:
    """Retrieve an impact analysis report for a regulation.

    Runs the impact analyzer agent against the knowledge graph.
    Currently returns a placeholder — full pipeline requires running
    Neo4j with seeded data.
    """
    return ImpactSummaryResponse(
        regulation_id=regulation_id,
        regulation_title=f"[Placeholder] Regulation {regulation_id}",
        total_requirements=0,
        affected_systems=0,
        gap_count=0,
        risk_level="unknown",
        details=[],
    )
