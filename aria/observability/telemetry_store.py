"""SQLite-backed telemetry persistence (shared by LLM, HTTP, and agent writers)."""

from __future__ import annotations

import math
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_db_path(raw: str | None) -> str:
    if raw is None:
        raw = os.environ.get("ARIA_TELEMETRY_DB", "aria_telemetry.db")
    if raw == ":memory:" or raw.startswith("file:"):
        return raw
    p = Path(raw)
    if not p.is_absolute():
        return str(_REPO_ROOT / p)
    return str(p)


def _utc_iso(ts: datetime | None = None) -> str:
    dt = ts or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    s = dt.isoformat()
    if s.endswith("+00:00"):
        return s[:-6] + "Z"
    return s


def _since_iso(since: datetime) -> str:
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    else:
        since = since.astimezone(timezone.utc)
    s = since.isoformat()
    if s.endswith("+00:00"):
        return s[:-6] + "Z"
    return s


def _percentile_linear(sorted_vals: list[float], p: float) -> float:
    """Linear interpolation percentile, p in [0, 100]."""
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    if p <= 0:
        return float(sorted_vals[0])
    if p >= 100:
        return float(sorted_vals[-1])
    k = (n - 1) * (p / 100.0)
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return float(sorted_vals[lo])
    return float(
        sorted_vals[lo] + (k - lo) * (sorted_vals[hi] - sorted_vals[lo]),
    )


class TelemetryStore:
    """WAL-mode SQLite store for LLM calls, HTTP requests, and agent executions."""

    def __init__(self, db_path: str | None = None) -> None:
        self._path = _resolve_db_path(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._init_schema()
            self._conn.commit()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS llm_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                cost_usd REAL,
                latency_ms REAL NOT NULL,
                status TEXT NOT NULL,
                error_type TEXT,
                attempt INTEGER NOT NULL,
                ts TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                latency_ms REAL NOT NULL,
                ts TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT,
                agent_name TEXT NOT NULL,
                status TEXT NOT NULL,
                error TEXT,
                duration_ms REAL NOT NULL,
                ts TEXT NOT NULL
            );
            """
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def record_llm_call(
        self,
        *,
        request_id: str,
        model: str,
        latency_ms: float,
        status: str,
        attempt: int,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        cost_usd: float | None = None,
        error_type: str | None = None,
        ts: datetime | None = None,
    ) -> None:
        row_ts = _utc_iso(ts)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO llm_calls (
                    request_id, model, prompt_tokens, completion_tokens,
                    cost_usd, latency_ms, status, error_type, attempt, ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    cost_usd,
                    latency_ms,
                    status,
                    error_type,
                    attempt,
                    row_ts,
                ),
            )
            self._conn.commit()

    def record_request(
        self,
        *,
        request_id: str,
        method: str,
        path: str,
        status_code: int,
        latency_ms: float,
        ts: datetime | None = None,
    ) -> None:
        row_ts = _utc_iso(ts)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO requests (
                    request_id, method, path, status_code, latency_ms, ts
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (request_id, method, path, status_code, latency_ms, row_ts),
            )
            self._conn.commit()

    def record_agent_execution(
        self,
        *,
        agent_name: str,
        status: str,
        duration_ms: float,
        request_id: str | None = None,
        error: str | None = None,
        ts: datetime | None = None,
    ) -> None:
        row_ts = _utc_iso(ts)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO agent_executions (
                    request_id, agent_name, status, error, duration_ms, ts
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (request_id, agent_name, status, error, duration_ms, row_ts),
            )
            self._conn.commit()

    def cost_summary(self, since: datetime) -> dict[str, Any]:
        cutoff = _since_iso(since)
        with self._lock:
            totals = self._conn.execute(
                """
                SELECT
                    COALESCE(SUM(prompt_tokens), 0) AS pt,
                    COALESCE(SUM(completion_tokens), 0) AS ct,
                    COALESCE(SUM(cost_usd), 0) AS cost
                FROM llm_calls
                WHERE ts >= ?
                """,
                (cutoff,),
            ).fetchone()
            by_model_rows = self._conn.execute(
                """
                SELECT
                    model,
                    COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                    COALESCE(SUM(cost_usd), 0) AS cost_usd
                FROM llm_calls
                WHERE ts >= ?
                GROUP BY model
                """,
                (cutoff,),
            ).fetchall()
        by_model: dict[str, dict[str, float | int]] = {}
        for r in by_model_rows:
            by_model[str(r["model"])] = {
                "prompt_tokens": int(r["prompt_tokens"]),
                "completion_tokens": int(r["completion_tokens"]),
                "cost_usd": float(r["cost_usd"]),
            }
        return {
            "total_prompt_tokens": int(totals["pt"]),
            "total_completion_tokens": int(totals["ct"]),
            "total_cost_usd": float(totals["cost"]),
            "by_model": by_model,
        }

    def request_summary(self, since: datetime) -> dict[str, Any]:
        cutoff = _since_iso(since)
        with self._lock:
            row = self._conn.execute(
                """
                SELECT COUNT(*) AS n,
                       SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) AS errs
                FROM requests
                WHERE ts >= ?
                """,
                (cutoff,),
            ).fetchone()
            lat_rows = self._conn.execute(
                """
                SELECT latency_ms FROM requests WHERE ts >= ?
                """,
                (cutoff,),
            ).fetchall()
        count = int(row["n"] or 0)
        errs = int(row["errs"] or 0)
        error_rate = (errs / count) if count else 0.0
        lats = [float(r["latency_ms"]) for r in lat_rows]
        lats.sort()
        return {
            "count": count,
            "error_rate": error_rate,
            "latency_ms": {
                "p50": _percentile_linear(lats, 50),
                "p95": _percentile_linear(lats, 95),
                "p99": _percentile_linear(lats, 99),
            },
        }

    def agent_summary(self, since: datetime) -> dict[str, Any]:
        cutoff = _since_iso(since)
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT
                    agent_name,
                    COUNT(*) AS n,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS ok,
                    AVG(duration_ms) AS avg_ms
                FROM agent_executions
                WHERE ts >= ?
                GROUP BY agent_name
                """,
                (cutoff,),
            ).fetchall()
        by_agent: dict[str, dict[str, float | int]] = {}
        for r in rows:
            n = int(r["n"])
            ok = int(r["ok"])
            by_agent[str(r["agent_name"])] = {
                "count": n,
                "success_rate": (ok / n) if n else 0.0,
                "avg_duration_ms": float(r["avg_ms"] or 0.0),
            }
        return {"by_agent": by_agent}

    def llm_error_rate(self, window_hours: int) -> float:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        cutoff_s = _since_iso(cutoff)
        with self._lock:
            row = self._conn.execute(
                """
                SELECT COUNT(*) AS n,
                       SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END) AS bad
                FROM llm_calls
                WHERE ts >= ?
                """,
                (cutoff_s,),
            ).fetchone()
        n = int(row["n"] or 0)
        bad = int(row["bad"] or 0)
        return (bad / n) if n else 0.0

    def telemetry_summary(self, since: datetime, *, period: str) -> dict[str, Any]:
        """Aggregate LLM, HTTP, and agent rows since ``since`` for GET /telemetry JSON."""
        cutoff = _since_iso(since)
        with self._lock:
            llm_row = self._conn.execute(
                """
                SELECT
                    COUNT(*) AS n,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS ok,
                    COALESCE(SUM(prompt_tokens), 0) AS pt,
                    COALESCE(SUM(completion_tokens), 0) AS ct,
                    COALESCE(SUM(cost_usd), 0) AS cost
                FROM llm_calls
                WHERE ts >= ?
                """,
                (cutoff,),
            ).fetchone()
            llm_lat_rows = self._conn.execute(
                "SELECT latency_ms FROM llm_calls WHERE ts >= ?",
                (cutoff,),
            ).fetchall()
            cost_by_model_rows = self._conn.execute(
                """
                SELECT model, COALESCE(SUM(cost_usd), 0) AS cost_usd
                FROM llm_calls
                WHERE ts >= ?
                GROUP BY model
                """,
                (cutoff,),
            ).fetchall()

            req_row = self._conn.execute(
                """
                SELECT COUNT(*) AS n,
                       SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) AS errs
                FROM requests
                WHERE ts >= ?
                """,
                (cutoff,),
            ).fetchone()
            req_lat_rows = self._conn.execute(
                "SELECT latency_ms FROM requests WHERE ts >= ?",
                (cutoff,),
            ).fetchall()
            by_path_rows = self._conn.execute(
                """
                SELECT path, COUNT(*) AS n
                FROM requests
                WHERE ts >= ?
                GROUP BY path
                """,
                (cutoff,),
            ).fetchall()

            agent_totals = self._conn.execute(
                """
                SELECT COUNT(*) AS n,
                       SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS ok
                FROM agent_executions
                WHERE ts >= ?
                """,
                (cutoff,),
            ).fetchone()
            agent_rows = self._conn.execute(
                """
                SELECT
                    agent_name,
                    COUNT(*) AS n,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS ok,
                    AVG(duration_ms) AS avg_ms
                FROM agent_executions
                WHERE ts >= ?
                GROUP BY agent_name
                """,
                (cutoff,),
            ).fetchall()

        llm_n = int(llm_row["n"] or 0)
        llm_ok = int(llm_row["ok"] or 0)
        llm_success_rate = (llm_ok / llm_n) if llm_n else 0.0
        llm_lats = sorted(float(r["latency_ms"]) for r in llm_lat_rows)

        cost_by_model: dict[str, float] = {}
        for r in cost_by_model_rows:
            cost_by_model[str(r["model"])] = float(r["cost_usd"])

        req_count = int(req_row["n"] or 0)
        req_errs = int(req_row["errs"] or 0)
        req_error_rate = (req_errs / req_count) if req_count else 0.0
        req_lats = sorted(float(r["latency_ms"]) for r in req_lat_rows)

        by_path: dict[str, int] = {}
        for r in by_path_rows:
            by_path[str(r["path"])] = int(r["n"])

        agent_n = int(agent_totals["n"] or 0)
        agent_ok = int(agent_totals["ok"] or 0)
        agent_success_rate = (agent_ok / agent_n) if agent_n else 0.0

        by_agent: dict[str, dict[str, float | int]] = {}
        for r in agent_rows:
            n = int(r["n"])
            ok = int(r["ok"])
            by_agent[str(r["agent_name"])] = {
                "count": n,
                "success_rate": (ok / n) if n else 0.0,
                "avg_ms": float(r["avg_ms"] or 0.0),
            }

        return {
            "period": period,
            "llm": {
                "total_calls": llm_n,
                "success_rate": llm_success_rate,
                "total_prompt_tokens": int(llm_row["pt"]),
                "total_completion_tokens": int(llm_row["ct"]),
                "total_cost_usd": float(llm_row["cost"]),
                "cost_by_model": cost_by_model,
                "p50_latency_ms": _percentile_linear(llm_lats, 50),
                "p95_latency_ms": _percentile_linear(llm_lats, 95),
            },
            "requests": {
                "total": req_count,
                "error_rate": req_error_rate,
                "p50_latency_ms": _percentile_linear(req_lats, 50),
                "p95_latency_ms": _percentile_linear(req_lats, 95),
                "by_path": by_path,
            },
            "agents": {
                "total_executions": agent_n,
                "success_rate": agent_success_rate,
                "by_agent": by_agent,
            },
        }


_store: TelemetryStore | None = None
_store_lock = threading.Lock()


def get_telemetry_store() -> TelemetryStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = TelemetryStore()
        return _store


def close_telemetry_store() -> None:
    global _store
    with _store_lock:
        if _store is not None:
            _store.close()
            _store = None
