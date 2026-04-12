"""Run full ingestion on a local file (parse → chunk → extract → graph → vectors).

Requires Neo4j, Chroma, and a reachable LLM (same checks as ``aria status``, plus LLM
must pass). Run ``aria init`` once so graph constraints exist, or omit ``--skip-schema``
to apply schema before ingest.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Annotated

import typer

from api.connections import connect_app_dependencies, disconnect_app_dependencies
from aria.health.assessment import (
    DependencyReport,
    assess_app_connections,
    full_ingest_dependencies_satisfied,
    merge_strict_connection_errors,
)
from aria.ingestion.pipeline import IngestionResult, IngestionStatus, ingest_document
from aria.ingestion.wiring import build_full_ingest_wiring


def _format_preflight_errors(report: DependencyReport) -> list[str]:
    lines: list[str] = []
    if not report.neo4j_ok:
        lines.append(f"neo4j: {report.errors.get('neo4j', 'unavailable')}")
    if not report.chroma_ok:
        lines.append(f"chroma: {report.errors.get('chroma', 'unavailable')}")
    if not report.llm_ok:
        lines.append(f"llm: {report.errors.get('llm', 'unavailable')}")
    return lines


def _ingestion_exit_code(result: IngestionResult) -> int:
    if result.status in (IngestionStatus.SUCCESS, IngestionStatus.SKIPPED_DUPLICATE):
        return 0
    return 1


def _print_result(path: Path, result: IngestionResult) -> None:
    print(f"{path}: {result.status.value}")
    if result.document_hash:
        print(f"  document_hash: {result.document_hash[:16]}…")
    print(f"  chunks: {result.chunks_produced}")
    print(f"  entities_extracted: {result.entities_extracted}")
    print(f"  graph_written: {result.graph_written}")
    print(f"  vector_indexed: {result.vector_indexed}")
    if result.errors:
        for err in result.errors:
            print(f"  error: {err}", file=sys.stderr)


async def _ingest_async(
    path: Path,
    *,
    force: bool,
    skip_schema: bool,
) -> int:
    conns = await connect_app_dependencies(strict=True)
    try:
        report = await assess_app_connections(conns)
        report = merge_strict_connection_errors(report, conns.connection_errors)
        if not full_ingest_dependencies_satisfied(report):
            print(
                "Full ingest requires Neo4j, Chroma, and LLM. Fix or start dependencies, "
                "then retry. (See `aria status`.)",
                file=sys.stderr,
            )
            for line in _format_preflight_errors(report):
                print(f"  missing: {line}", file=sys.stderr)
            return 1

        neo = conns.neo4j
        vs = conns.vector_store
        if neo is None or vs is None:
            print("Internal error: assessment passed but connections are missing.", file=sys.stderr)
            return 1

        if not skip_schema:
            await neo.initialize_schema()

        wiring = build_full_ingest_wiring(neo, vs)
        result = await ingest_document(
            path,
            entity_extractor=wiring.entity_extractor,
            graph_writer=wiring.graph_writer,
            vector_indexer=wiring.vector_indexer,
            neo4j_dedup=neo,
            force=force,
        )
        _print_result(path, result)
        return _ingestion_exit_code(result)
    finally:
        await disconnect_app_dependencies(conns)


def ingest(
    file: Annotated[
        Path,
        typer.Argument(
            ...,
            exists=True,
            dir_okay=False,
            readable=True,
            help="PDF or HTML file to ingest.",
        ),
    ],
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-ingest even if this content hash was already processed.",
    ),
    skip_schema: bool = typer.Option(
        False,
        "--skip-schema",
        help=(
            "Do not run Neo4j schema initialization before ingest "
            "(use if `aria init` was already applied)."
        ),
    ),
) -> None:
    """Ingest a document through the full pipeline (LLM extraction, Neo4j, Chroma)."""
    code = asyncio.run(_ingest_async(file, force=force, skip_schema=skip_schema))
    raise typer.Exit(code)
