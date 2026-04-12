"""Tests for ``aria.observability.since_parse``."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aria.observability.since_parse import parse_since_iso_utc


def test_parse_z_suffix_utc() -> None:
    dt = parse_since_iso_utc("2025-04-01T00:00:00Z")
    assert dt == datetime(2025, 4, 1, 0, 0, 0, tzinfo=UTC)


def test_parse_naive_becomes_utc() -> None:
    dt = parse_since_iso_utc("2025-04-01T12:30:00")
    assert dt.tzinfo == UTC


def test_parse_invalid_raises() -> None:
    with pytest.raises(ValueError, match="ISO8601"):
        parse_since_iso_utc("not-a-date")
