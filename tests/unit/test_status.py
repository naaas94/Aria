"""Unit tests for ``aria status`` human-readable ingest/LLM note (no live backends)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria.cli.commands import status as status_mod
from aria.health.assessment import DependencyReport

_REPORT_OK = DependencyReport(neo4j_ok=True, chroma_ok=True, llm_ok=False)


@pytest.mark.asyncio
async def test_status_human_output_includes_ingest_llm_note(capsys) -> None:
    mock_conns = MagicMock()
    mock_conns.connection_errors = {}

    with (
        patch(
            "aria.cli.commands.status.connect_app_dependencies",
            new_callable=AsyncMock,
            return_value=mock_conns,
        ),
        patch(
            "aria.cli.commands.status.assess_app_connections",
            new_callable=AsyncMock,
            return_value=_REPORT_OK,
        ),
        patch(
            "aria.cli.commands.status.disconnect_app_dependencies",
            new_callable=AsyncMock,
        ),
        patch(
            "aria.cli.commands.status.merge_strict_connection_errors",
            return_value=_REPORT_OK,
        ),
    ):
        code = await status_mod._status_async(as_json=False)

    assert code == 0
    out = capsys.readouterr().out
    assert status_mod._STATUS_INGEST_LLM_NOTE in out


@pytest.mark.asyncio
async def test_status_json_output_omits_human_ingest_note(capsys) -> None:
    mock_conns = MagicMock()
    mock_conns.connection_errors = {}

    with (
        patch(
            "aria.cli.commands.status.connect_app_dependencies",
            new_callable=AsyncMock,
            return_value=mock_conns,
        ),
        patch(
            "aria.cli.commands.status.assess_app_connections",
            new_callable=AsyncMock,
            return_value=_REPORT_OK,
        ),
        patch(
            "aria.cli.commands.status.disconnect_app_dependencies",
            new_callable=AsyncMock,
        ),
        patch(
            "aria.cli.commands.status.merge_strict_connection_errors",
            return_value=_REPORT_OK,
        ),
    ):
        code = await status_mod._status_async(as_json=True)

    assert code == 0
    out = capsys.readouterr().out
    assert status_mod._STATUS_INGEST_LLM_NOTE not in out
    assert '"neo4j_ok"' in out
