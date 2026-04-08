"""Record and load replay fixtures for deterministic golden-set regression.

A *replay fixture* captures the full request/response payload from a live
E2E run so that subsequent CI runs can validate contract, retrieval, and
quality checks **without** hitting live infrastructure.

Fixtures are stored as JSON in ``replay/`` and referenced from golden YAML
cases via ``expect.replay.fixture_file``.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPLAY_DIR = Path(__file__).resolve().parent / "replay"

_SCRUB_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*\S+"),
    re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
]


def _scrub(text: str) -> str:
    """Remove secrets and PII-like patterns from text."""
    for pat in _SCRUB_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


def _scrub_dict(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, str):
            out[k] = _scrub(v)
        elif isinstance(v, dict):
            out[k] = _scrub_dict(v)
        elif isinstance(v, list):
            out[k] = [_scrub_dict(i) if isinstance(i, dict) else (_scrub(i) if isinstance(i, str) else i) for i in v]
        else:
            out[k] = v
    return out


def _git_short_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


@dataclass
class ReplayFixture:
    """Serializable snapshot of a single E2E request/response cycle."""

    case_id: str
    correlation_id: str
    recorded_at: str = ""
    aria_commit: str = ""
    request: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] = field(default_factory=dict)
    strategy_used: str = ""


class EvalRecorder:
    """Captures request/response pairs and writes scrubbed replay fixtures."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._dir = output_dir or REPLAY_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._fixtures: list[ReplayFixture] = []

    def record(
        self,
        case_id: str,
        correlation_id: str,
        request: dict[str, Any],
        response: dict[str, Any],
        strategy: str,
    ) -> ReplayFixture:
        fixture = ReplayFixture(
            case_id=case_id,
            correlation_id=correlation_id,
            recorded_at=datetime.now(timezone.utc).isoformat(),
            aria_commit=_git_short_sha(),
            request=_scrub_dict(request),
            response=_scrub_dict(response),
            strategy_used=strategy,
        )
        self._fixtures.append(fixture)
        return fixture

    def flush(self) -> list[Path]:
        """Write all captured fixtures to disk and return the paths."""
        paths: list[Path] = []
        for fix in self._fixtures:
            path = self._dir / f"{fix.case_id}.json"
            path.write_text(
                json.dumps(asdict(fix), indent=2, default=str),
                encoding="utf-8",
            )
            paths.append(path)
        self._fixtures.clear()
        return paths


def load_replay_fixture(fixture_file: str) -> ReplayFixture:
    """Load a replay fixture from ``replay/{fixture_file}``."""
    path = REPLAY_DIR / fixture_file
    if not path.exists():
        raise FileNotFoundError(f"Replay fixture not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ReplayFixture(**raw)
