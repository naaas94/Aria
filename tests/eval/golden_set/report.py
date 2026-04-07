"""Golden-set run report — JSON and optional JUnit XML output."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring

from .runner import CheckOutcome


@dataclass
class CaseResult:
    golden_id: str
    category: str
    checks: dict[str, CheckOutcome] = field(default_factory=dict)


@dataclass
class GoldenReport:
    """Accumulates results across all golden cases in a session."""

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    tier: str = "fast"
    results: list[CaseResult] = field(default_factory=list)
    _index: dict[str, CaseResult] = field(default_factory=dict, repr=False)

    def record(self, golden_id: str, category: str, checks: dict[str, CheckOutcome]) -> None:
        entry = CaseResult(golden_id=golden_id, category=category, checks=checks)
        self.results.append(entry)
        self._index[golden_id] = entry

    # -- JSON ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        total = len(self.results)
        failed = sum(
            1 for r in self.results if any(not c.passed for c in r.checks.values())
        )
        return {
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tier": self.tier,
            "results": [
                {
                    "golden_id": r.golden_id,
                    "category": r.category,
                    "checks": {
                        name: {
                            "passed": c.passed,
                            "duration_ms": round(c.duration_ms, 2),
                            "detail": c.detail,
                            "sub_checks": c.sub_checks,
                        }
                        for name, c in r.checks.items()
                    },
                }
                for r in self.results
            ],
            "summary": {
                "total": total,
                "passed": total - failed,
                "failed": failed,
            },
        }

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    # -- JUnit XML -------------------------------------------------------------

    def to_junit_xml(self) -> bytes:
        suite = Element("testsuite")
        suite.set("name", "golden_set")
        suite.set("tests", str(len(self.results)))

        failures = 0
        total_time = 0.0

        for r in self.results:
            for check_name, outcome in r.checks.items():
                tc = SubElement(suite, "testcase")
                tc.set("name", f"{r.golden_id}::{check_name}")
                tc.set("classname", f"golden_set.{r.category}")
                tc.set("time", f"{outcome.duration_ms / 1000:.4f}")
                total_time += outcome.duration_ms

                if not outcome.passed:
                    failures += 1
                    fail_el = SubElement(tc, "failure")
                    fail_el.set("message", outcome.detail)
                    fail_el.text = json.dumps(outcome.sub_checks, indent=2)

        suite.set("failures", str(failures))
        suite.set("time", f"{total_time / 1000:.4f}")
        return tostring(suite, encoding="unicode").encode("utf-8")

    def write_junit(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.to_junit_xml())
