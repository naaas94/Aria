"""Tests for ``connect_app_dependencies(strict=...)``."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.connections import connect_app_dependencies


@pytest.mark.asyncio
async def test_strict_neo4j_connect_failure_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    with (
        patch("api.connections.Neo4jClient") as neo_cls,
        patch("api.connections.VectorStore") as vs_cls,
    ):
        inst = neo_cls.return_value
        inst.connect = AsyncMock(side_effect=RuntimeError("bolt failed"))
        vs_cls.return_value.connect = MagicMock()
        conns = await connect_app_dependencies(strict=True)
    assert conns.neo4j is None
    assert "bolt failed" in conns.connection_errors.get("neo4j", "")


@pytest.mark.asyncio
async def test_strict_chroma_failure_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEO4J_URI", raising=False)
    with patch("api.connections.VectorStore") as vs_cls:
        vs_cls.return_value.connect.side_effect = OSError("chroma down")
        conns = await connect_app_dependencies(strict=True)
    assert conns.vector_store is None
    assert "chroma down" in conns.connection_errors.get("chroma", "")


@pytest.mark.asyncio
async def test_non_strict_does_not_fill_connection_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NEO4J_URI", raising=False)
    with patch("api.connections.VectorStore") as vs_cls:
        vs_cls.return_value.connect.side_effect = OSError("chroma down")
        conns = await connect_app_dependencies()
    assert conns.connection_errors == {}
