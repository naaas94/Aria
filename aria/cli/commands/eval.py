"""Run golden-set pytest target; forwards extra args to pytest."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GOLDEN_TEST = _REPO_ROOT / "tests" / "eval" / "golden_set" / "test_goldens.py"


def run_golden_eval(ctx: typer.Context) -> None:
    """Run ``tests/eval/golden_set/test_goldens.py``; extra CLI tokens are passed to pytest."""
    cmd = [sys.executable, "-m", "pytest", str(_GOLDEN_TEST), *ctx.args]
    raise typer.Exit(subprocess.run(cmd).returncode)
