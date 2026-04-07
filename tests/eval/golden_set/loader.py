"""Discover and validate YAML golden-set case files.

The loader walks ``cases/`` subdirectories under the golden-set root,
parses each ``.yaml`` file into a :class:`GoldenCase`, and optionally
cross-checks against ``manifest.yaml`` for completeness.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .schema import GoldenCase

GOLDEN_SET_ROOT = Path(__file__).resolve().parent
CASES_DIR = GOLDEN_SET_ROOT / "cases"
MANIFEST_PATH = GOLDEN_SET_ROOT / "manifest.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)  # type: ignore[return-value]


def load_golden_cases(*, root: Path | None = None) -> list[GoldenCase]:
    """Load and validate every ``*.yaml`` case file under *root*/cases/.

    Returns a list sorted by case ``id`` for deterministic parametrization.
    """
    cases_dir = (root or GOLDEN_SET_ROOT) / "cases"
    cases: list[GoldenCase] = []
    for yaml_path in sorted(cases_dir.rglob("*.yaml")):
        raw = _load_yaml(yaml_path)
        try:
            case = GoldenCase.model_validate(raw)
        except Exception as exc:
            raise ValueError(f"Invalid golden case {yaml_path}: {exc}") from exc
        cases.append(case)

    ids = [c.id for c in cases]
    dupes = {x for x in ids if ids.count(x) > 1}
    if dupes:
        raise ValueError(f"Duplicate golden case ids: {dupes}")

    return sorted(cases, key=lambda c: c.id)


def load_manifest(*, path: Path | None = None) -> dict[str, Any]:
    """Load the manifest index and return it as a raw dict."""
    return _load_yaml(path or MANIFEST_PATH)


def validate_manifest_coverage(
    cases: list[GoldenCase],
    manifest: dict[str, Any],
) -> list[str]:
    """Return a list of warnings for mismatches between manifest and cases."""
    warnings: list[str] = []
    manifest_ids: set[str] = set()
    for entry in manifest.get("cases", []):
        manifest_ids.add(entry["id"])

    case_ids = {c.id for c in cases}
    for mid in sorted(manifest_ids - case_ids):
        warnings.append(f"Manifest lists '{mid}' but no YAML case file found")
    for cid in sorted(case_ids - manifest_ids):
        warnings.append(f"Case '{cid}' exists but is not in manifest.yaml")

    return warnings
