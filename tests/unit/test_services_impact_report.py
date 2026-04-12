"""Unit tests for ``aria.services.impact_report`` (mocked agent / Neo4j)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria.contracts.impact import ImpactReport
from aria.services.impact_report import (
    ImpactReportSuccess,
    ImpactReportUnavailable,
    run_impact_report,
)


@pytest.mark.asyncio
async def test_placeholder_impact() -> None:
    conns = MagicMock(neo4j=None)
    out = await run_impact_report("reg-p", conns, use_placeholder=True)
    assert isinstance(out, ImpactReportSuccess)
    assert out.aria_mode == "placeholder"
    assert out.response.regulation_id == "reg-p"
    assert "[Placeholder]" in out.response.regulation_title


@pytest.mark.asyncio
async def test_live_missing_neo4j() -> None:
    conns = MagicMock(neo4j=None)
    out = await run_impact_report("reg-x", conns, use_placeholder=False)
    assert isinstance(out, ImpactReportUnavailable)
    assert out.missing_dependencies == ["neo4j"]


@pytest.mark.asyncio
async def test_live_success_via_mocked_agent() -> None:
    report = ImpactReport(
        regulation_id="reg-live",
        regulation_title="EU AI Act",
        total_requirements=0,
        affected_systems=[],
        remediation_tasks=[],
        coverage_summary={},
    )
    neo = MagicMock()
    conns = MagicMock(neo4j=neo)

    with patch("aria.services.impact_report.ImpactAnalyzerAgent") as impact_agent_cls:
        impact_agent_cls.return_value.process = AsyncMock(return_value=report.model_dump())
        out = await run_impact_report("reg-live", conns, use_placeholder=False)

    assert isinstance(out, ImpactReportSuccess)
    assert out.aria_mode == "live"
    assert out.response.regulation_id == "reg-live"
    assert out.response.regulation_title == "EU AI Act"
    impact_agent_cls.assert_called_once()
