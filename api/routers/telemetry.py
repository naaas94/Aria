"""Observability: Prometheus scrape and JSON telemetry summary."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aria.observability.metrics  # noqa: F401
from fastapi import APIRouter, HTTPException, Query
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from aria.observability.telemetry_store import get_telemetry_store

router = APIRouter(tags=["observability"])


def _parse_since_iso(raw: str) -> datetime:
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="Invalid since: expected ISO8601 datetime",
        ) from exc
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/telemetry")
async def telemetry_json(
    since: str | None = Query(
        None,
        description=(
            "ISO8601 start of the window (e.g. 2025-04-01T00:00:00Z). "
            "When set, overrides the rolling hours window."
        ),
    ),
    hours: int = Query(
        24,
        ge=1,
        le=8760,
        description="Rolling window length in hours when since is omitted.",
    ),
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    if since is not None and since.strip() != "":
        start = _parse_since_iso(since)
        period = f"since_{since.strip()}"
    else:
        start = now - timedelta(hours=hours)
        period = f"last_{hours}h"
    return get_telemetry_store().telemetry_summary(start, period=period)
