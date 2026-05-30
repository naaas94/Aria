"""Unit tests for ``aria serve`` port defaults (no live uvicorn)."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from aria.cli.main import app

runner = CliRunner()


def test_serve_help_documents_api_port_override() -> None:
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "API_PORT" in result.stdout
    assert "8080" in result.stdout


@patch("aria.cli.main.load_dotenv")
@patch("aria.cli.commands.serve.uvicorn.run")
def test_serve_default_port_8080_without_api_port(mock_run, _mock_dotenv, monkeypatch) -> None:
    monkeypatch.delenv("API_PORT", raising=False)
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 0
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["port"] == 8080


@patch("aria.cli.main.load_dotenv")
@patch("aria.cli.commands.serve.uvicorn.run")
def test_serve_api_port_env_overrides_default(mock_run, _mock_dotenv, monkeypatch) -> None:
    monkeypatch.setenv("API_PORT", "9090")
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 0
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["port"] == 9090


@patch("aria.cli.main.load_dotenv")
@patch("aria.cli.commands.serve.uvicorn.run")
def test_serve_cli_port_used_when_api_port_unset(mock_run, _mock_dotenv, monkeypatch) -> None:
    monkeypatch.delenv("API_PORT", raising=False)
    result = runner.invoke(app, ["serve", "--port", "3000"])
    assert result.exit_code == 0
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["port"] == 3000
