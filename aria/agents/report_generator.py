"""Report generator agent — structured output generation.

Receives an ImpactReport from the Impact Analyzer and generates
a human-readable Markdown compliance report plus a JSON task payload.
"""

from __future__ import annotations

from typing import Any

from aria.agents.base import BaseAgent
from aria.contracts.impact import CoverageStatus, ImpactReport
from aria.llm.client import LLMClient
from aria.llm.prompts.report_generation import (
    REPORT_GENERATION_SYSTEM,
    REPORT_GENERATION_USER,
)


class ReportGeneratorAgent(BaseAgent):
    name = "report_generator"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        super().__init__()
        self._llm = llm_client or LLMClient()

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        report = ImpactReport.model_validate(input_data)

        detailed_findings = self._format_findings(report)

        try:
            markdown_report = await self._generate_with_llm(report, detailed_findings)
        except Exception:
            self.logger.warning("LLM report generation failed, using template fallback")
            markdown_report = self._generate_template(report)

        task_payload = [t.model_dump() for t in report.remediation_tasks]

        return {
            "markdown_report": markdown_report,
            "task_payload": task_payload,
            "summary": {
                "regulation": report.regulation_title,
                "total_requirements": report.total_requirements,
                "gap_count": report.gap_count,
                "risk_level": report.risk_level,
            },
        }

    async def _generate_with_llm(
        self, report: ImpactReport, detailed_findings: str
    ) -> str:
        messages = [
            {"role": "system", "content": REPORT_GENERATION_SYSTEM},
            {
                "role": "user",
                "content": REPORT_GENERATION_USER.format(
                    regulation_title=report.regulation_title,
                    total_requirements=report.total_requirements,
                    systems_affected=len(report.affected_systems),
                    gap_count=report.gap_count,
                    risk_level=report.risk_level,
                    detailed_findings=detailed_findings,
                ),
            },
        ]
        return await self._llm.complete(messages)

    def _format_findings(self, report: ImpactReport) -> str:
        lines = []
        for asset in report.affected_systems:
            status_marker = "GAP" if asset.coverage_status == CoverageStatus.GAP else "OK"
            line = (
                f"[{status_marker}] {asset.system_name} ({asset.owner_team}): "
                f"{asset.requirement_text}"
            )
            if asset.covering_policy_title:
                line += f" — covered by: {asset.covering_policy_title}"
            lines.append(line)
        return "\n".join(lines)

    def _generate_template(self, report: ImpactReport) -> str:
        """Deterministic template fallback when LLM is unavailable."""
        lines = [
            f"# Compliance Report: {report.regulation_title}",
            "",
            "## Executive Summary",
            f"Analysis of {report.total_requirements} requirements identified "
            f"{report.gap_count} compliance gap(s). Overall risk: **{report.risk_level}**.",
            "",
            "## Affected Systems",
            "",
        ]

        for asset in report.affected_systems:
            emoji = "X" if asset.coverage_status == CoverageStatus.GAP else "V"
            lines.append(
                f"- [{emoji}] **{asset.system_name}** ({asset.owner_team}): "
                f"{asset.requirement_text[:80]}"
            )

        if report.remediation_tasks:
            lines.extend(["", "## Remediation Tasks", ""])
            for task in report.remediation_tasks:
                lines.append(
                    f"- [{task.priority}] **{task.title}** — assigned to {task.assigned_team}"
                )

        return "\n".join(lines)
