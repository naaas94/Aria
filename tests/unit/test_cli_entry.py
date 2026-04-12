"""Smoke tests for the ``aria`` Typer CLI (no live backends)."""

from __future__ import annotations

from typer.testing import CliRunner

from aria.cli.main import app

runner = CliRunner()


def test_root_help_exits_zero() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ARIA" in result.stdout


def test_query_help_lists_options() -> None:
    result = runner.invoke(app, ["query", "--help"])
    assert result.exit_code == 0
    assert "--regulation-id" in result.stdout or "-r" in result.stdout
