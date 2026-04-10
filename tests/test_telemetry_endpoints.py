"""Tests for GET /metrics (Prometheus) and GET /telemetry (JSON summary)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient

from aria.observability.telemetry_store import close_telemetry_store, get_telemetry_store


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ARIA_TELEMETRY_DB", ":memory:")
    close_telemetry_store()

    from api.main import app

    with TestClient(app) as c:
        yield c


def test_metrics_returns_prometheus_text(client: TestClient) -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200
    ct = resp.headers.get("content-type", "")
    assert "text/plain" in ct
    body = resp.text
    assert "# HELP" in body or "# TYPE" in body
    assert "aria_" in body


def test_telemetry_json_schema_empty_window(client: TestClient) -> None:
    resp = client.get("/telemetry")
    assert resp.status_code == 200
    data = resp.json()
    assert data["period"] == "last_24h"
    llm = data["llm"]
    assert llm["total_calls"] == 0
    assert llm["success_rate"] == 0.0
    assert llm["total_prompt_tokens"] == 0
    assert llm["total_completion_tokens"] == 0
    assert llm["total_cost_usd"] == 0.0
    assert llm["cost_by_model"] == {}
    assert llm["p50_latency_ms"] == 0.0
    assert llm["p95_latency_ms"] == 0.0
    req = data["requests"]
    assert req["total"] == 0
    assert req["error_rate"] == 0.0
    assert req["by_path"] == {}
    agents = data["agents"]
    assert agents["total_executions"] == 0
    assert agents["success_rate"] == 0.0
    assert agents["by_agent"] == {}


def test_telemetry_hours_query_param(client: TestClient) -> None:
    resp = client.get("/telemetry?hours=48")
    assert resp.status_code == 200
    assert resp.json()["period"] == "last_48h"


def test_telemetry_since_query_param(client: TestClient) -> None:
    resp = client.get("/telemetry?since=2025-04-01T00:00:00Z")
    assert resp.status_code == 200
    assert resp.json()["period"] == "since_2025-04-01T00:00:00Z"


def test_telemetry_invalid_since_422(client: TestClient) -> None:
    resp = client.get("/telemetry?since=not-a-timestamp")
    assert resp.status_code == 422


def test_telemetry_aggregates_from_store(client: TestClient) -> None:
    store = get_telemetry_store()
    t = datetime.now(timezone.utc)
    store.record_llm_call(
        request_id="r1",
        model="gpt-4o",
        latency_ms=100.0,
        status="success",
        attempt=1,
        prompt_tokens=100,
        completion_tokens=50,
        cost_usd=0.5,
        ts=t,
    )
    store.record_llm_call(
        request_id="r2",
        model="ollama/llama3.2",
        latency_ms=300.0,
        status="error",
        attempt=1,
        ts=t,
    )
    store.record_request(
        request_id="r1",
        method="POST",
        path="/query",
        status_code=200,
        latency_ms=10.0,
        ts=t,
    )
    store.record_request(
        request_id="r2",
        method="POST",
        path="/ingest",
        status_code=500,
        latency_ms=20.0,
        ts=t,
    )
    store.record_agent_execution(
        agent_name="compliance_agent",
        status="success",
        duration_ms=1000.0,
        request_id="r1",
        ts=t,
    )
    store.record_agent_execution(
        agent_name="remediation_agent",
        status="error",
        duration_ms=2000.0,
        request_id="r2",
        ts=t,
    )

    resp = client.get("/telemetry?hours=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["llm"]["total_calls"] == 2
    assert data["llm"]["success_rate"] == pytest.approx(0.5)
    assert data["llm"]["total_prompt_tokens"] == 100
    assert data["llm"]["total_completion_tokens"] == 50
    assert data["llm"]["total_cost_usd"] == pytest.approx(0.5)
    assert data["llm"]["cost_by_model"]["gpt-4o"] == pytest.approx(0.5)
    assert data["llm"]["cost_by_model"]["ollama/llama3.2"] == pytest.approx(0.0)
    assert data["requests"]["total"] == 2
    assert data["requests"]["error_rate"] == pytest.approx(0.5)
    assert data["requests"]["by_path"]["/query"] == 1
    assert data["requests"]["by_path"]["/ingest"] == 1
    assert data["agents"]["total_executions"] == 2
    assert data["agents"]["success_rate"] == pytest.approx(0.5)
    assert data["agents"]["by_agent"]["compliance_agent"]["count"] == 1
    assert data["agents"]["by_agent"]["compliance_agent"]["success_rate"] == pytest.approx(1.0)
    assert data["agents"]["by_agent"]["remediation_agent"]["success_rate"] == pytest.approx(0.0)


def test_telemetry_respects_since_cutoff(client: TestClient) -> None:
    store = get_telemetry_store()
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    new = datetime.now(timezone.utc)
    store.record_llm_call(
        request_id="old",
        model="m",
        latency_ms=1.0,
        status="success",
        attempt=1,
        ts=old,
    )
    store.record_llm_call(
        request_id="new",
        model="m",
        latency_ms=2.0,
        status="success",
        attempt=1,
        ts=new,
    )
    since = (new - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    resp = client.get(f"/telemetry?since={since}")
    assert resp.status_code == 200
    assert resp.json()["llm"]["total_calls"] == 1
