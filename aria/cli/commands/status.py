"""Print dependency status (Neo4j, Chroma, LLM) using shared assessment logic."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import typer

from api.connections import connect_app_dependencies, disconnect_app_dependencies
from aria.health.assessment import (
    DependencyReport,
    assess_app_connections,
    merge_strict_connection_errors,
)


def _print_table(report: DependencyReport) -> None:
    rows = [
        ("neo4j", report.neo4j_ok),
        ("chroma", report.chroma_ok),
        ("llm", report.llm_ok),
    ]
    w = max(len(name) for name, _ in rows)
    for name, ok in rows:
        err = report.errors.get(name)
        line = f"{name.ljust(w)}  {'ok' if ok else 'fail'}"
        if err:
            line += f"  ({err})"
        print(line)


def _report_payload(report: DependencyReport) -> dict[str, Any]:
    return {
        "neo4j_ok": report.neo4j_ok,
        "chroma_ok": report.chroma_ok,
        "llm_ok": report.llm_ok,
        "errors": report.errors,
    }


async def _status_async(*, as_json: bool) -> int:
    conns = await connect_app_dependencies(strict=True)
    try:
        report = await assess_app_connections(conns)
        report = merge_strict_connection_errors(report, conns.connection_errors)
        if as_json:
            print(json.dumps(_report_payload(report), indent=2, sort_keys=True))
        else:
            _print_table(report)
        neo_chroma_ok = report.neo4j_ok and report.chroma_ok
        return 0 if neo_chroma_ok else 1
    finally:
        await disconnect_app_dependencies(conns)


def status(
    as_json: bool = typer.Option(False, "--json", help="Print JSON instead of a text table."),
) -> None:
    """Check Neo4j, Chroma, and LLM reachability (strict connect + health probes)."""
    code = asyncio.run(_status_async(as_json=as_json))
    raise typer.Exit(code)
