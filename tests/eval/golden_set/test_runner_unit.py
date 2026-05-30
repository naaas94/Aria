"""Fast unit tests for golden-set runner lens checks (no golden-tier fixture)."""

from __future__ import annotations

from unittest.mock import patch

from tests.eval.golden_set.recorder import ReplayFixture
from tests.eval.golden_set.runner import run_replay_check, run_retrieval_check
from tests.eval.golden_set.schema import Expectations, ExpectReplay, ExpectRetrieval, GoldenCase


def _retrieval_case(
    *,
    requires_multi_hop: bool,
    retrieved_context: str,
) -> GoldenCase:
    return GoldenCase(
        id="unit-retrieval",
        category="happy",
        tier="fast",
        input={"retrieved_context": retrieved_context},
        expect=Expectations(
            retrieval=ExpectRetrieval(
                expected_components=["system_name"],
                requires_multi_hop=requires_multi_hop,
                component_keywords={"system_name": ["crm"]},
            )
        ),
    )


def test_run_retrieval_check_passes_with_keywords() -> None:
    case = _retrieval_case(
        requires_multi_hop=True,
        retrieved_context="The crm system handles customer records.",
    )
    outcome = run_retrieval_check(case)
    assert outcome.passed is True
    assert "multi_hop_declared" not in outcome.sub_checks


def test_run_retrieval_check_fails_empty_context() -> None:
    case = _retrieval_case(requires_multi_hop=True, retrieved_context="")
    outcome = run_retrieval_check(case)
    assert outcome.passed is False


def test_run_retrieval_check_requires_multi_hop_does_not_affect_outcome() -> None:
    context = "crm platform in use"
    with_flag = run_retrieval_check(
        _retrieval_case(requires_multi_hop=True, retrieved_context=context)
    )
    without_flag = run_retrieval_check(
        _retrieval_case(requires_multi_hop=False, retrieved_context=context)
    )
    assert with_flag.passed == without_flag.passed
    assert with_flag.sub_checks.keys() == without_flag.sub_checks.keys()


def test_run_replay_check_passes_with_inline_fixture() -> None:
    fixture = ReplayFixture(
        case_id="eval-replay-unit",
        correlation_id="corr-unit-1",
        recorded_at="2026-05-30T00:00:00+00:00",
        aria_commit="deadbeef",
        request={"question": "test"},
        response={
            "answer": "GDPR erasure right applies to personal data.",
            "retrieval_strategy": "graphrag",
            "sources": [{"chunk_id": "c1", "text": "Article 17"}],
            "trace": {"retrieval": {"strategy": "graphrag"}},
        },
        strategy_used="graphrag",
    )
    case = GoldenCase(
        id="eval-replay-unit",
        category="happy",
        tier="fast",
        expect=Expectations(
            replay=ExpectReplay(
                fixture_file="unused-inline.json",
                expected_strategy="graphrag",
                min_source_count=1,
                required_trace_keys=["retrieval"],
            )
        ),
    )
    with patch(
        "tests.eval.golden_set.recorder.load_replay_fixture",
        return_value=fixture,
    ):
        outcome = run_replay_check(case)
    assert outcome.passed is True


def test_run_replay_check_fails_when_fixture_missing() -> None:
    case = GoldenCase(
        id="eval-replay-missing",
        category="happy",
        tier="fast",
        expect=Expectations(
            replay=ExpectReplay(fixture_file="no-such-fixture.json"),
        ),
    )
    with patch(
        "tests.eval.golden_set.recorder.load_replay_fixture",
        side_effect=FileNotFoundError("Replay fixture not found"),
    ):
        outcome = run_replay_check(case)
    assert outcome.passed is False
    assert outcome.sub_checks.get("fixture_exists") is False
