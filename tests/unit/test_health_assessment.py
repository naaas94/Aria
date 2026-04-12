"""Unit tests for ``aria.health.assessment`` (mocked backends, no real LLM)."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria.health.assessment import (
    DependencyReport,
    assess_app_connections,
    full_ingest_dependencies_satisfied,
    merge_strict_connection_errors,
    probe_llm_reachable,
)


@dataclass
class _FakeConns:
    neo4j: object | None
    vector_store: object | None


@pytest.mark.asyncio
async def test_assess_all_disconnected_reports_errors() -> None:
    with patch("aria.health.assessment.probe_llm_reachable", new_callable=AsyncMock) as probe:
        probe.return_value = (False, "llm down")
        report = await assess_app_connections(_FakeConns(neo4j=None, vector_store=None))
    assert report == DependencyReport(
        neo4j_ok=False,
        chroma_ok=False,
        llm_ok=False,
        errors={
            "neo4j": "not configured",
            "chroma": "not configured",
            "llm": "llm down",
        },
    )


@pytest.mark.asyncio
async def test_assess_neo4j_and_chroma_ok_llm_mocked_ok() -> None:
    neo = MagicMock()
    neo.health_check = AsyncMock(return_value=True)
    vs = MagicMock()
    vs.health_check = MagicMock(return_value=True)
    with patch("aria.health.assessment.probe_llm_reachable", new_callable=AsyncMock) as probe:
        probe.return_value = (True, None)
        report = await assess_app_connections(_FakeConns(neo4j=neo, vector_store=vs))
    assert report.neo4j_ok is True
    assert report.chroma_ok is True
    assert report.llm_ok is True
    assert report.errors == {}


@pytest.mark.asyncio
async def test_assess_neo4j_health_raises() -> None:
    neo = MagicMock()
    neo.health_check = AsyncMock(side_effect=RuntimeError("bolt failed"))
    vs = MagicMock()
    vs.health_check = MagicMock(return_value=True)
    with patch("aria.health.assessment.probe_llm_reachable", new_callable=AsyncMock) as probe:
        probe.return_value = (True, None)
        report = await assess_app_connections(_FakeConns(neo4j=neo, vector_store=vs))
    assert report.neo4j_ok is False
    assert report.chroma_ok is True
    assert "neo4j" in report.errors


@pytest.mark.asyncio
async def test_probe_llm_reachable_accepts_minimal_completion() -> None:
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="x"))]

    with (
        patch("aria.health.assessment.litellm.acompletion", new_callable=AsyncMock) as ac,
        patch.dict(
            "os.environ",
            {
                "LLM_MODEL": "ollama/llama3.2",
                "LLM_BASE_URL": "http://127.0.0.1:11434",
                "LLM_API_KEY": "not-needed",
            },
            clear=False,
        ),
    ):
        ac.return_value = fake_resp
        ok, err = await probe_llm_reachable()
    assert ok is True
    assert err is None
    ac.assert_awaited_once()
    call_kw = ac.await_args.kwargs
    assert call_kw["max_tokens"] == 1
    assert call_kw["timeout"] == 12.0


def test_full_ingest_dependencies_satisfied_requires_all_three() -> None:
    assert full_ingest_dependencies_satisfied(
        DependencyReport(neo4j_ok=True, chroma_ok=True, llm_ok=True),
    )
    assert not full_ingest_dependencies_satisfied(
        DependencyReport(neo4j_ok=True, chroma_ok=True, llm_ok=False),
    )
    assert not full_ingest_dependencies_satisfied(
        DependencyReport(neo4j_ok=False, chroma_ok=True, llm_ok=True),
    )


def test_merge_strict_connection_errors_replaces_not_configured() -> None:
    base = DependencyReport(
        neo4j_ok=False,
        chroma_ok=False,
        llm_ok=True,
        errors={"neo4j": "not configured", "chroma": "not configured"},
    )
    merged = merge_strict_connection_errors(
        base,
        {"neo4j": "ConnectionRefusedError: refused", "chroma": "OSError: down"},
    )
    assert merged.errors["neo4j"] == "ConnectionRefusedError: refused"
    assert merged.errors["chroma"] == "OSError: down"
