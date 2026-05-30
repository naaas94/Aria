"""Unit tests for ``aria.cli.commands.ingest`` (no live Neo4j/Chroma/LLM)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria.cli.commands import ingest as ingest_mod
from aria.health.assessment import DependencyReport
from aria.ingestion.pipeline import IngestionResult, IngestionStatus


def _satisfied_report() -> DependencyReport:
    return DependencyReport(neo4j_ok=True, chroma_ok=True, llm_ok=True)


@pytest.mark.asyncio
async def test_fetch_regulation_ids_returns_string_ids() -> None:
    neo = AsyncMock()
    neo.execute_read.return_value = [{"id": "reg-a"}, {"id": "reg-b"}]
    ids = await ingest_mod._fetch_regulation_ids(neo)
    assert ids == ["reg-a", "reg-b"]
    neo.execute_read.assert_awaited_once_with("MATCH (r:Regulation) RETURN r.id AS id")


@pytest.mark.asyncio
async def test_fetch_regulation_ids_skips_records_without_id() -> None:
    neo = AsyncMock()
    neo.execute_read.return_value = [{"id": "reg-a"}, {}, {"id": None}]
    ids = await ingest_mod._fetch_regulation_ids(neo)
    assert ids == ["reg-a"]


@pytest.mark.asyncio
async def test_ingest_async_prints_regulation_ids_when_graph_written(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    path = tmp_path / "doc.html"
    path.write_text("<html></html>", encoding="utf-8")
    result = IngestionResult(
        status=IngestionStatus.SUCCESS,
        graph_written=True,
        document_hash="abc",
    )
    mock_neo = AsyncMock()
    mock_neo.initialize_schema = AsyncMock()
    conns = MagicMock()
    conns.neo4j = mock_neo
    conns.vector_store = MagicMock()
    conns.connection_errors = {}

    with (
        patch.object(ingest_mod, "connect_app_dependencies", AsyncMock(return_value=conns)),
        patch.object(ingest_mod, "disconnect_app_dependencies", AsyncMock()),
        patch.object(ingest_mod, "assess_app_connections", AsyncMock(return_value=_satisfied_report())),
        patch.object(ingest_mod, "merge_strict_connection_errors", side_effect=lambda r, _e: r),
        patch.object(ingest_mod, "build_full_ingest_wiring", return_value=MagicMock()),
        patch.object(ingest_mod, "ingest_document", AsyncMock(return_value=result)),
        patch.object(
            ingest_mod,
            "_fetch_regulation_ids",
            AsyncMock(return_value=["reg-one", "reg-two"]),
        ) as fetch_mock,
    ):
        code = await ingest_mod._ingest_async(path, force=False, skip_schema=False)

    assert code == 0
    fetch_mock.assert_awaited_once_with(mock_neo)
    assert "regulation_ids: reg-one, reg-two" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_ingest_async_prints_none_warning_when_no_regulation_nodes(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    path = tmp_path / "doc.html"
    path.write_text("<html></html>", encoding="utf-8")
    result = IngestionResult(status=IngestionStatus.SUCCESS, graph_written=True)
    mock_neo = AsyncMock()
    mock_neo.initialize_schema = AsyncMock()
    conns = MagicMock()
    conns.neo4j = mock_neo
    conns.vector_store = MagicMock()
    conns.connection_errors = {}

    with (
        patch.object(ingest_mod, "connect_app_dependencies", AsyncMock(return_value=conns)),
        patch.object(ingest_mod, "disconnect_app_dependencies", AsyncMock()),
        patch.object(ingest_mod, "assess_app_connections", AsyncMock(return_value=_satisfied_report())),
        patch.object(ingest_mod, "merge_strict_connection_errors", side_effect=lambda r, _e: r),
        patch.object(ingest_mod, "build_full_ingest_wiring", return_value=MagicMock()),
        patch.object(ingest_mod, "ingest_document", AsyncMock(return_value=result)),
        patch.object(ingest_mod, "_fetch_regulation_ids", AsyncMock(return_value=[])),
    ):
        await ingest_mod._ingest_async(path, force=False, skip_schema=True)

    out = capsys.readouterr().out
    assert "regulation_ids: (none — Regulation nodes not found" in out


@pytest.mark.asyncio
async def test_ingest_async_skips_regulation_fetch_when_graph_not_written(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    path = tmp_path / "doc.html"
    path.write_text("<html></html>", encoding="utf-8")
    result = IngestionResult(
        status=IngestionStatus.SKIPPED_DUPLICATE,
        graph_written=False,
    )
    mock_neo = AsyncMock()
    conns = MagicMock()
    conns.neo4j = mock_neo
    conns.vector_store = MagicMock()
    conns.connection_errors = {}

    with (
        patch.object(ingest_mod, "connect_app_dependencies", AsyncMock(return_value=conns)),
        patch.object(ingest_mod, "disconnect_app_dependencies", AsyncMock()),
        patch.object(ingest_mod, "assess_app_connections", AsyncMock(return_value=_satisfied_report())),
        patch.object(ingest_mod, "merge_strict_connection_errors", side_effect=lambda r, _e: r),
        patch.object(ingest_mod, "build_full_ingest_wiring", return_value=MagicMock()),
        patch.object(ingest_mod, "ingest_document", AsyncMock(return_value=result)),
        patch.object(ingest_mod, "_fetch_regulation_ids", AsyncMock()) as fetch_mock,
    ):
        code = await ingest_mod._ingest_async(path, force=False, skip_schema=True)

    assert code == 0
    fetch_mock.assert_not_called()
    assert "regulation_ids:" not in capsys.readouterr().out
