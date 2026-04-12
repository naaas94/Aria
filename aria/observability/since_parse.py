"""Parse ISO8601 ``since`` values for telemetry windows (API + CLI, no FastAPI dependency)."""

from __future__ import annotations

from datetime import UTC, datetime


def parse_since_iso_utc(raw: str) -> datetime:
    """Parse ``raw`` as UTC-aware datetime. Raises ``ValueError`` if invalid."""
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as exc:
        raise ValueError(
            f"Invalid since: expected ISO8601 datetime, got {raw!r}",
        ) from exc
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
