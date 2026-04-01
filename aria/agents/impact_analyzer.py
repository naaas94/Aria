"""Impact analyzer agent — multi-hop graph traversal for impact assessment.

Receives a regulation ID, executes multi-hop Cypher traversals via
MCP-shaped tool ports, and produces a structured ImpactReport.
"""

from __future__ import annotations

from typing import Any

from aria.agents.base import BaseAgent
from aria.contracts.impact import (
    AffectedAsset,
    CoverageStatus,
    ImpactReport,
    RemediationTask,
    RiskLevel,
)


class ImpactAnalyzerAgent(BaseAgent):
    name = "impact_analyzer"

    def __init__(self, graph_query_fn: Any | None = None) -> None:
        super().__init__()
        self._query_fn = graph_query_fn

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        regulation_id = input_data.get("regulation_id")
        if not regulation_id:
            raise ValueError("No regulation_id provided to impact analyzer")

        if self._query_fn:
            impact_rows = await self._query_fn(
                "impact_by_regulation", {"regulation_id": regulation_id}
            )
        else:
            impact_rows = input_data.get("impact_data", [])

        affected, tasks = self._build_impact(regulation_id, impact_rows)

        coverage_summary = {}
        for asset in affected:
            coverage_summary[asset.coverage_status] = (
                coverage_summary.get(asset.coverage_status, 0) + 1
            )

        report = ImpactReport(
            regulation_id=regulation_id,
            regulation_title=impact_rows[0].get("regulation", "") if impact_rows else "",
            total_requirements=len(impact_rows),
            affected_systems=affected,
            remediation_tasks=tasks,
            coverage_summary=coverage_summary,
        )

        self.logger.info(
            "Impact analysis: %d assets, %d gaps, risk=%s",
            len(affected), report.gap_count, report.risk_level,
        )

        return report.model_dump()

    def _build_impact(
        self, regulation_id: str, rows: list[dict[str, Any]]
    ) -> tuple[list[AffectedAsset], list[RemediationTask]]:
        affected: list[AffectedAsset] = []
        tasks: list[RemediationTask] = []

        for i, row in enumerate(rows):
            has_policy = bool(row.get("policy_id"))
            status = CoverageStatus.COVERED if has_policy else CoverageStatus.GAP

            affected.append(
                AffectedAsset(
                    system_id=row.get("system_id", f"sys-{i}"),
                    system_name=row.get("system_name", "Unknown"),
                    owner_team=row.get("team", "Unknown"),
                    requirement_id=row.get("requirement_id", f"req-{i}"),
                    requirement_text=row.get("requirement", ""),
                    coverage_status=status,
                    covering_policy_id=row.get("policy_id"),
                    covering_policy_title=row.get("policy_title"),
                )
            )

            if status == CoverageStatus.GAP:
                priority = self._assess_priority(row)
                tasks.append(
                    RemediationTask(
                        id=f"task-{regulation_id}-{i}",
                        title=f"Address gap: {row.get('requirement', '')[:60]}",
                        description=(
                            f"Requirement '{row.get('requirement', '')}' affects "
                            f"system '{row.get('system_name', '')}' but has no "
                            f"addressing policy. Team '{row.get('team', '')}' "
                            f"should create or update coverage."
                        ),
                        priority=priority,
                        assigned_team=row.get("team_id", row.get("team", "")),
                        requirement_id=row.get("requirement_id", f"req-{i}"),
                        system_id=row.get("system_id", f"sys-{i}"),
                    )
                )

        return affected, tasks

    def _assess_priority(self, row: dict[str, Any]) -> RiskLevel:
        obligation = row.get("obligation_type", "")
        if obligation in ("prohibition", "assessment"):
            return RiskLevel.HIGH
        if obligation == "disclosure":
            return RiskLevel.MEDIUM
        return RiskLevel.MEDIUM
