"""Print telemetry summary JSON (same window logic as GET /telemetry)."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta

import typer

from aria.observability.since_parse import parse_since_iso_utc
from aria.observability.telemetry_store import get_telemetry_store


def telemetry_cli(
    since: str | None = typer.Option(
        None,
        "--since",
        help="ISO8601 start of window (overrides --hours when set).",
    ),
    hours: int = typer.Option(
        24,
        "--hours",
        min=1,
        max=8760,
        help="Rolling window in hours when --since is omitted.",
    ),
) -> None:
    """Print aggregated telemetry (LLM, HTTP, agents) for the selected window."""
    now = datetime.now(UTC)
    if since is not None and since.strip() != "":
        try:
            start = parse_since_iso_utc(since)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            raise typer.Exit(2) from exc
        period = f"since_{since.strip()}"
    else:
        start = now - timedelta(hours=hours)
        period = f"last_{hours}h"
    store = get_telemetry_store()
    data = store.telemetry_summary(start, period=period)
    print(json.dumps(data, indent=2, default=str))
