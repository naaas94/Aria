"""Impact analysis and remediation task contracts.

Produced by the Impact Analyzer agent and consumed by the Report Generator.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from aria.contracts._strict import enforce_schema_version_if_configured

SCHEMA_VERSION = "0.1.0"


class CoverageStatus(StrEnum):
    COVERED = "covered"
    PARTIAL = "partial"
    GAP = "gap"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AffectedAsset(BaseModel):
    """A system or process affected by a regulatory requirement."""

    system_id: str
    system_name: str
    owner_team: str
    requirement_id: str
    requirement_text: str
    coverage_status: CoverageStatus
    covering_policy_id: str | None = None
    covering_policy_title: str | None = None


class ImpactAnalysisRequest(BaseModel):
    """Input to the impact analyzer agent — scopes graph traversal to one regulation."""

    regulation_id: str = Field(..., description="Regulation node id in the knowledge graph")


class RemediationTask(BaseModel):
    """A concrete action item for addressing a compliance gap."""

    id: str
    title: str
    description: str
    priority: RiskLevel
    assigned_team: str
    deadline: date | None = None
    requirement_id: str
    system_id: str


class ImpactReport(BaseModel):
    """Full impact analysis for a regulation or article."""

    schema_version: str = SCHEMA_VERSION
    regulation_id: str
    regulation_title: str
    total_requirements: int = 0
    affected_systems: list[AffectedAsset] = Field(default_factory=list)
    remediation_tasks: list[RemediationTask] = Field(default_factory=list)
    coverage_summary: dict[CoverageStatus, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _align_total_requirements_with_gap_count(self) -> ImpactReport:
        """If upstream left ``total_requirements`` at 0 but reported gaps, align counts.

        Avoids a misleading risk ratio (e.g. gaps / 1) when totals were omitted.
        """
        gaps = self.coverage_summary.get(CoverageStatus.GAP, 0)
        if gaps > 0 and self.total_requirements == 0:
            self.total_requirements = gaps
        return self

    @property
    def gap_count(self) -> int:
        return self.coverage_summary.get(CoverageStatus.GAP, 0)

    @property
    def risk_level(self) -> RiskLevel:
        if self.gap_count == 0:
            return RiskLevel.LOW
        denom = max(self.total_requirements, self.gap_count, 1)
        ratio = self.gap_count / denom
        if ratio > 0.5:
            return RiskLevel.CRITICAL
        if ratio > 0.25:
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM

    @model_validator(mode="after")
    def _strict_schema_version(self) -> ImpactReport:
        enforce_schema_version_if_configured(self)
        return self
