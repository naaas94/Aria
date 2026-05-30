"""Integration tests for HTTP request telemetry middleware."""

from __future__ import annotations

import pytest

from prometheus_client import REGISTRY

from aria.observability.metrics import HTTP_REQUEST_COUNTER
from aria.observability.telemetry_store import close_telemetry_store, get_telemetry_store


def _counter_value(method: str, status_code: str) -> float:
    return HTTP_REQUEST_COUNTER.labels(method=method, status_code=status_code)._value.get()


def _http_duration_histogram_count(method: str, status_code: str) -> float:
    value = REGISTRY.get_sample_value(
        "aria_http_request_duration_seconds_count",
        {"method": method, "status_code": status_code},
    )
    return float(value or 0.0)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ARIA_TELEMETRY_DB", ":memory:")
    close_telemetry_store()

    from starlette.testclient import TestClient

    from api.main import app

    with TestClient(app) as c:
        yield c


def test_skips_noise_paths(client) -> None:
    store = get_telemetry_store()
    for path in ("/health", "/ready", "/metrics", "/telemetry"):
        client.get(path)
    rows = store._conn.execute("SELECT COUNT(*) AS n FROM requests").fetchone()  # noqa: SLF001
    assert int(rows["n"]) == 0


def test_records_unknown_route_with_status_and_request_id(client) -> None:
    before = _counter_value("GET", "404")
    store = get_telemetry_store()
    rid = "custom-req-id-99"
    client.get("/definitely-not-a-route", headers={"X-Request-ID": rid})
    row = store._conn.execute(  # noqa: SLF001
        "SELECT request_id, method, path, status_code FROM requests WHERE request_id = ?",
        (rid,),
    ).fetchone()
    assert row is not None
    assert row["method"] == "GET"
    assert row["path"] == "/definitely-not-a-route"
    assert row["status_code"] == 404
    assert _counter_value("GET", "404") == before + 1


def test_records_multiple_requests(client) -> None:
    store = get_telemetry_store()
    client.get("/missing-one")
    client.get("/missing-two")
    n = store._conn.execute("SELECT COUNT(*) AS n FROM requests").fetchone()  # noqa: SLF001
    assert int(n["n"]) == 2


def test_latency_non_negative(client) -> None:
    store = get_telemetry_store()
    client.get("/any-missing")
    row = store._conn.execute("SELECT latency_ms FROM requests LIMIT 1").fetchone()  # noqa: SLF001
    assert row is not None
    assert float(row["latency_ms"]) >= 0.0


def test_http_request_duration_histogram_observed(client) -> None:
    before = _http_duration_histogram_count("GET", "404")
    client.get("/definitely-not-a-route")
    assert _http_duration_histogram_count("GET", "404") == before + 1.0


def test_skipped_paths_do_not_observe_http_duration_histogram(client) -> None:
    before = sum(
        _http_duration_histogram_count(method, status)
        for method in ("GET",)
        for status in ("200", "404")
    )
    for path in ("/health", "/ready", "/metrics", "/telemetry"):
        client.get(path)
    after = sum(
        _http_duration_histogram_count(method, status)
        for method in ("GET",)
        for status in ("200", "404")
    )
    assert after == before
