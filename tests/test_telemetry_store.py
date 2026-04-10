"""Unit tests for SQLite telemetry store."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aria.observability import telemetry_store as ts_mod
from aria.observability.telemetry_store import (
    TelemetryStore,
    close_telemetry_store,
    get_telemetry_store,
)


def _iso(hours_ago: float = 0.0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours_ago)


@pytest.fixture
def store() -> TelemetryStore:
    return TelemetryStore(":memory:")


def test_llm_call_roundtrip(store: TelemetryStore) -> None:
    t = _iso()
    store.record_llm_call(
        request_id="req-1",
        model="m1",
        latency_ms=12.5,
        status="success",
        attempt=1,
        prompt_tokens=10,
        completion_tokens=20,
        cost_usd=0.01,
        ts=t,
    )
    row = store._conn.execute(  # noqa: SLF001
        "SELECT * FROM llm_calls WHERE request_id = ?",
        ("req-1",),
    ).fetchone()
    assert row is not None
    assert row["model"] == "m1"
    assert row["prompt_tokens"] == 10
    assert row["completion_tokens"] == 20
    assert row["cost_usd"] == pytest.approx(0.01)
    assert row["latency_ms"] == pytest.approx(12.5)
    assert row["status"] == "success"
    assert row["attempt"] == 1


def test_request_roundtrip(store: TelemetryStore) -> None:
    t = _iso()
    store.record_request(
        request_id="r2",
        method="GET",
        path="/x",
        status_code=200,
        latency_ms=3.0,
        ts=t,
    )
    row = store._conn.execute(
        "SELECT * FROM requests WHERE request_id = ?",
        ("r2",),
    ).fetchone()
    assert row is not None
    assert row["method"] == "GET"
    assert row["path"] == "/x"
    assert row["status_code"] == 200


def test_agent_execution_roundtrip(store: TelemetryStore) -> None:
    t = _iso()
    store.record_agent_execution(
        agent_name="a1",
        status="success",
        duration_ms=100.0,
        request_id=None,
        ts=t,
    )
    row = store._conn.execute(
        "SELECT * FROM agent_executions WHERE agent_name = ?",
        ("a1",),
    ).fetchone()
    assert row is not None
    assert row["request_id"] is None
    assert row["status"] == "success"


def test_cost_summary_aggregates(store: TelemetryStore) -> None:
    base = _iso(1)
    store.record_llm_call(
        request_id="a",
        model="m-a",
        latency_ms=1.0,
        status="success",
        attempt=1,
        prompt_tokens=100,
        completion_tokens=50,
        cost_usd=0.5,
        ts=base,
    )
    store.record_llm_call(
        request_id="b",
        model="m-a",
        latency_ms=1.0,
        status="error",
        attempt=2,
        prompt_tokens=10,
        completion_tokens=None,
        cost_usd=None,
        ts=base,
    )
    store.record_llm_call(
        request_id="c",
        model="m-b",
        latency_ms=2.0,
        status="success",
        attempt=1,
        prompt_tokens=1,
        completion_tokens=2,
        cost_usd=0.25,
        ts=base,
    )
    since = base - timedelta(seconds=1)
    out = store.cost_summary(since)
    assert out["total_prompt_tokens"] == 111
    assert out["total_completion_tokens"] == 52
    assert out["total_cost_usd"] == pytest.approx(0.75)
    assert out["by_model"]["m-a"]["prompt_tokens"] == 110
    assert out["by_model"]["m-a"]["cost_usd"] == pytest.approx(0.5)
    assert out["by_model"]["m-b"]["completion_tokens"] == 2


def test_request_summary_aggregates(store: TelemetryStore) -> None:
    base = _iso(0.5)
    for i, code in enumerate([200, 200, 404, 500]):
        store.record_request(
            request_id=f"rid-{i}",
            method="GET",
            path="/p",
            status_code=code,
            latency_ms=float(10 * (i + 1)),
            ts=base,
        )
    since = base - timedelta(seconds=10)
    out = store.request_summary(since)
    assert out["count"] == 4
    assert out["error_rate"] == pytest.approx(0.5)
    assert out["latency_ms"]["p50"] == pytest.approx(25.0)
    assert out["latency_ms"]["p95"] == pytest.approx(38.5)
    assert out["latency_ms"]["p99"] == pytest.approx(39.7)


def test_tables_idempotent(tmp_path) -> None:
    path = tmp_path / "telemetry.db"
    TelemetryStore(str(path))
    TelemetryStore(str(path))


def test_singleton_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARIA_TELEMETRY_DB", ":memory:")
    close_telemetry_store()
    a = get_telemetry_store()
    b = get_telemetry_store()
    assert a is b
    close_telemetry_store()
    assert ts_mod._store is None  # noqa: SLF001


def test_agent_summary_aggregates(store: TelemetryStore) -> None:
    base = _iso(0.25)
    for _ in range(3):
        store.record_agent_execution(
            agent_name="alpha",
            status="success",
            duration_ms=100.0,
            ts=base,
        )
    store.record_agent_execution(
        agent_name="alpha",
        status="error",
        duration_ms=200.0,
        error="boom",
        ts=base,
    )
    store.record_agent_execution(
        agent_name="beta",
        status="success",
        duration_ms=50.0,
        ts=base,
    )
    since = base - timedelta(seconds=5)
    out = store.agent_summary(since)
    alpha = out["by_agent"]["alpha"]
    assert alpha["count"] == 4
    assert alpha["success_rate"] == pytest.approx(0.75)
    assert alpha["avg_duration_ms"] == pytest.approx(125.0)
    beta = out["by_agent"]["beta"]
    assert beta["count"] == 1
    assert beta["success_rate"] == pytest.approx(1.0)


def test_prune_older_than_removes_stale_rows(store: TelemetryStore) -> None:
    old = datetime.now(timezone.utc) - timedelta(days=90)
    recent = datetime.now(timezone.utc) - timedelta(days=1)
    store.record_llm_call(
        request_id="old",
        model="m",
        latency_ms=1.0,
        status="success",
        attempt=1,
        ts=old,
    )
    store.record_request(
        request_id="old-req",
        method="GET",
        path="/",
        status_code=200,
        latency_ms=1.0,
        ts=old,
    )
    store.record_agent_execution(
        agent_name="a",
        status="success",
        duration_ms=1.0,
        ts=old,
    )
    store.record_request(
        request_id="new-req",
        method="POST",
        path="/x",
        status_code=201,
        latency_ms=2.0,
        ts=recent,
    )
    counts = store.prune_older_than(retention_days=30, vacuum=False)
    assert counts["llm_calls"] == 1
    assert counts["requests"] == 1
    assert counts["agent_executions"] == 1
    assert (
        store._conn.execute("SELECT COUNT(*) AS n FROM llm_calls").fetchone()["n"] == 0  # noqa: SLF001
    )
    assert store._conn.execute("SELECT COUNT(*) AS n FROM requests").fetchone()["n"] == 1  # noqa: SLF001
    assert (
        store._conn.execute("SELECT COUNT(*) AS n FROM agent_executions").fetchone()["n"]
        == 0
    )


def test_llm_error_rate(store: TelemetryStore) -> None:
    now = datetime.now(timezone.utc)
    store.record_llm_call(
        request_id="x",
        model="m",
        latency_ms=1.0,
        status="success",
        attempt=1,
        ts=now - timedelta(minutes=1),
    )
    store.record_llm_call(
        request_id="y",
        model="m",
        latency_ms=1.0,
        status="error",
        attempt=1,
        ts=now - timedelta(minutes=2),
    )
    assert store.llm_error_rate(24) == pytest.approx(0.5)
