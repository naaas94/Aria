"""Parametrized pytest driver for the centralized golden set.

Loads every YAML case under ``cases/``, validates against the
:class:`GoldenCase` schema, and runs whichever expectation lenses
(contract / trace / retrieval / security) each case declares.

Results are collected by the session-scoped ``golden_report`` fixture
and written to ``golden_report.json`` + ``golden_report.xml`` on teardown.

Run::

    pytest tests/eval/golden_set/test_goldens.py -v -m golden
    pytest tests/eval/golden_set/test_goldens.py --golden-tier=fast -v
"""

from __future__ import annotations

import pytest

from .conftest import TIER_ORDER
from .loader import load_golden_cases, load_manifest, validate_manifest_coverage
from .report import GoldenReport
from .runner import (
    CheckOutcome,
    run_contract_check,
    run_quality_check,
    run_replay_check,
    run_retrieval_check,
    run_security_check,
    run_trace_check,
)
from .schema import GoldenCase

_CASES = load_golden_cases()


@pytest.mark.eval
@pytest.mark.golden
@pytest.mark.parametrize("case", _CASES, ids=lambda c: c.id)
def test_golden(case: GoldenCase, golden_tier: str, golden_report: GoldenReport) -> None:
    max_tier = TIER_ORDER.get(golden_tier, 2)
    case_tier = TIER_ORDER.get(case.tier, 0)
    if case_tier > max_tier:
        pytest.skip(f"Case tier '{case.tier}' exceeds requested max '{golden_tier}'")

    results: dict[str, CheckOutcome] = {}

    if case.expect.contract:
        results["contract"] = run_contract_check(case)

    if case.expect.trace:
        results["trace"] = run_trace_check(case)

    if case.expect.retrieval:
        results["retrieval"] = run_retrieval_check(case)

    if case.expect.security:
        results["security"] = run_security_check(case)

    if case.expect.quality:
        results["quality"] = run_quality_check(case)

    if case.expect.replay:
        results["replay"] = run_replay_check(case)

    golden_report.record(case.id, case.category, results, case_input=case.input)

    failures = {name: r for name, r in results.items() if not r.passed}

    if case.category == "behavior_must_not":
        if not failures:
            pytest.fail(
                f"{case.id}: behavior_must_not case passed all checks — "
                "the violation was not detected"
            )
    elif failures:
        details = "; ".join(f"{n}: {r.detail}" for n, r in failures.items())
        pytest.fail(f"{case.id} failed — {details}")


@pytest.mark.golden
def test_manifest_coverage() -> None:
    """Ensure manifest.yaml and case files on disk stay in sync."""
    cases = load_golden_cases()
    manifest = load_manifest()
    warnings = validate_manifest_coverage(cases, manifest)
    if warnings:
        pytest.fail("Manifest / case drift:\n  " + "\n  ".join(warnings))
