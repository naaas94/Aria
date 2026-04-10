"""Integration tests for agent run() telemetry persistence."""

from __future__ import annotations

from typing import Any

import pytest
import structlog

from aria.agents.base import BaseAgent
from aria.observability import telemetry_store as ts_mod
from aria.observability.telemetry_store import close_telemetry_store, get_telemetry_store


class TrivialAgent(BaseAgent):
    name = "telemetry_trivial"

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {"echo": input_data}


@pytest.fixture
def isolated_telemetry_store(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ARIA_TELEMETRY_DB", ":memory:")
    close_telemetry_store()
    yield get_telemetry_store()
    close_telemetry_store()
    assert ts_mod._store is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_run_records_agent_execution_row(isolated_telemetry_store) -> None:
    structlog.contextvars.bind_contextvars(request_id="corr-agent-1")
    try:
        agent = TrivialAgent()
        result = await agent.run({"x": 1})

        assert result.success
        row = isolated_telemetry_store._conn.execute(  # noqa: SLF001
            "SELECT * FROM agent_executions WHERE agent_name = ?",
            (TrivialAgent.name,),
        ).fetchone()
        assert row is not None
        assert row["request_id"] == "corr-agent-1"
        assert row["status"] == "success"
        assert row["error"] is None
        assert row["duration_ms"] == pytest.approx(result.duration_ms)
    finally:
        structlog.contextvars.unbind_contextvars("request_id")


@pytest.mark.asyncio
async def test_run_error_records_agent_execution_row(isolated_telemetry_store) -> None:
    class FailingAgent(BaseAgent):
        name = "telemetry_fail"

        async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
            raise ValueError("expected failure")

    agent = FailingAgent()
    result = await agent.run({})

    assert not result.success
    row = isolated_telemetry_store._conn.execute(  # noqa: SLF001
        "SELECT * FROM agent_executions WHERE agent_name = ?",
        ("telemetry_fail",),
    ).fetchone()
    assert row is not None
    assert row["status"] == "error"
    assert "expected failure" in (row["error"] or "")
