"""Pytest configuration for the golden-set evaluation suite.

Adds ``--golden-tier`` CLI option, session-scoped report fixture, and
tier-based skip logic so ``-m eval --golden-tier=fast`` skips medium/slow cases.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .report import GoldenReport

TIER_ORDER = {"fast": 0, "medium": 1, "slow": 2}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--golden-tier",
        default="slow",
        choices=["fast", "medium", "slow"],
        help="Maximum tier to run (fast < medium < slow). Default: slow (run all).",
    )
    parser.addoption(
        "--golden-report-dir",
        default=None,
        help="Directory for golden_report.json / golden_report.xml output.",
    )
    parser.addoption(
        "--emit-eval-store",
        action="store_true",
        default=False,
        help="Write each golden result to the offline eval store (eval_runs/).",
    )


@pytest.fixture(scope="session")
def golden_tier(request: pytest.FixtureRequest) -> str:
    return request.config.getoption("--golden-tier")  # type: ignore[return-value]


@pytest.fixture(scope="session")
def golden_report(request: pytest.FixtureRequest) -> GoldenReport:
    """Session-scoped report that collects all golden-set results.

    On teardown it writes ``golden_report.json`` (and ``.xml``) to the
    report directory (``--golden-report-dir`` or the project root).
    """
    tier: str = request.config.getoption("--golden-tier")  # type: ignore[assignment]
    emit_store: bool = request.config.getoption("--emit-eval-store")  # type: ignore[assignment]
    report = GoldenReport(tier=tier, emit_eval_store=emit_store)
    yield report  # type: ignore[misc]

    report_dir_opt = request.config.getoption("--golden-report-dir")
    if report_dir_opt:
        report_dir = Path(report_dir_opt)
    else:
        report_dir = Path(__file__).resolve().parents[3]

    if report.results:
        report.write_json(report_dir / "golden_report.json")
        report.write_junit(report_dir / "golden_report.xml")
