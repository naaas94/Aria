"""LLM client writes token/cost/latency rows to the telemetry store."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog.contextvars

from aria.observability import telemetry_store as ts_mod
from aria.observability.telemetry_store import TelemetryStore, close_telemetry_store


@pytest.fixture
def telemetry_store(monkeypatch: pytest.MonkeyPatch) -> TelemetryStore:
    close_telemetry_store()
    monkeypatch.setenv("ARIA_TELEMETRY_DB", ":memory:")
    store = ts_mod.get_telemetry_store()
    yield store
    close_telemetry_store()


def _mock_success_response(
    *,
    content: str = "ok",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    response_cost: float = 0.002,
) -> MagicMock:
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    resp._hidden_params = {"response_cost": response_cost}
    return resp


@pytest.mark.asyncio
async def test_complete_records_llm_call_with_tokens_cost_latency(
    telemetry_store: TelemetryStore,
) -> None:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id="corr-req-42")

    mock_response = _mock_success_response()

    with (
        patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_response),
        patch("aria.llm.client.time") as mock_time,
    ):
        mock_time.monotonic.side_effect = [1000.0, 1000.05]
        from aria.llm.client import LLMClient

        client = LLMClient()
        out = await client.complete([{"role": "user", "content": "Hi"}])

    assert out == "ok"
    row = telemetry_store._conn.execute(  # noqa: SLF001
        "SELECT * FROM llm_calls WHERE request_id = ?",
        ("corr-req-42",),
    ).fetchone()
    assert row is not None
    assert row["model"] == "ollama/llama3.2"
    assert row["prompt_tokens"] == 100
    assert row["completion_tokens"] == 50
    assert row["cost_usd"] == pytest.approx(0.002)
    assert row["latency_ms"] == pytest.approx(50.0)
    assert row["status"] == "success"
    assert row["attempt"] == 1
    assert row["error_type"] is None


@pytest.mark.asyncio
async def test_complete_failure_records_error_row(
    telemetry_store: TelemetryStore,
) -> None:
    structlog.contextvars.clear_contextvars()

    with patch("litellm.acompletion", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
        from aria.llm.client import LLMClient

        client = LLMClient(max_retries=1)
        with pytest.raises(RuntimeError, match="boom"):
            await client.complete([{"role": "user", "content": "Hi"}])

    row = telemetry_store._conn.execute(
        "SELECT * FROM llm_calls",
    ).fetchone()
    assert row is not None
    assert row["status"] == "error"
    assert row["error_type"] == "RuntimeError"
    assert row["prompt_tokens"] is None
    assert row["completion_tokens"] is None
    assert row["cost_usd"] is None
    assert row["request_id"] == ""


@pytest.mark.asyncio
async def test_complete_timeout_records_timeout_status(
    telemetry_store: TelemetryStore,
) -> None:
    structlog.contextvars.clear_contextvars()

    with patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        side_effect=TimeoutError("deadline"),
    ):
        from aria.llm.client import LLMClient

        client = LLMClient(max_retries=1)
        with pytest.raises(TimeoutError):
            await client.complete([{"role": "user", "content": "Hi"}])

    row = telemetry_store._conn.execute(
        "SELECT * FROM llm_calls",
    ).fetchone()
    assert row is not None
    assert row["status"] == "timeout"
    assert row["error_type"] == "TimeoutError"
