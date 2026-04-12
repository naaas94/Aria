"""Run a compliance query in-process (same logic as ``POST /query``).

Live mode (``ARIA_PLACEHOLDER_API=false``) uses the same dependency rules as the API:
Chroma is required for all live paths; Neo4j is required when ``--graph-rag`` is on.
Process environment should match the API (``ARIA_PLACEHOLDER_API``, ``NEO4J_*``, Chroma
settings used by ``VectorStore``). Use ``aria status`` to verify backends.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Annotated, Any

import typer

from api.config import placeholder_api_enabled
from api.connections import (
    AppConnections,
    connect_app_dependencies,
    disconnect_app_dependencies,
)
from aria.services.compliance_query import (
    ComplianceQueryRequest,
    ComplianceQuerySuccess,
    ComplianceQueryUnavailable,
    run_compliance_query,
)


def _print_human_success(outcome: ComplianceQuerySuccess) -> None:
    print(outcome.response.answer)
    if outcome.response.sources:
        print()
        print("Sources:")
        for i, src in enumerate(outcome.response.sources, 1):
            score = src.get("score")
            text = src.get("text", "")
            preview = text if len(text) <= 400 else text[:397] + "…"
            if score is not None:
                print(f"  [{i}] (score={score}) {preview}")
            else:
                print(f"  [{i}] {preview}")


def _success_payload(outcome: ComplianceQuerySuccess) -> dict[str, Any]:
    return {
        "answer": outcome.response.answer,
        "sources": outcome.response.sources,
        "retrieval_strategy": outcome.response.retrieval_strategy,
        "trace": outcome.response.trace,
        "aria_mode": outcome.aria_mode,
    }


async def _query_async(
    *,
    question: str,
    regulation_id: str | None,
    use_graph_rag: bool,
    top_k: int,
    as_json: bool,
) -> int:
    req = ComplianceQueryRequest(
        question=question,
        regulation_id=regulation_id,
        use_graph_rag=use_graph_rag,
        top_k=top_k,
    )
    use_placeholder = placeholder_api_enabled()
    if use_placeholder:
        conns = AppConnections()
        outcome = await run_compliance_query(req, conns, use_placeholder=True)
    else:
        conns = await connect_app_dependencies(strict=True)
        try:
            outcome = await run_compliance_query(req, conns, use_placeholder=False)
        finally:
            await disconnect_app_dependencies(conns)

    if isinstance(outcome, ComplianceQueryUnavailable):
        body = {
            "detail": outcome.detail,
            "code": "service_unavailable",
            "missing_dependencies": outcome.missing_dependencies,
        }
        if as_json:
            print(json.dumps(body, indent=2, sort_keys=True))
        else:
            print(outcome.detail, file=sys.stderr)
            print(
                f"Missing dependencies: {', '.join(outcome.missing_dependencies)}",
                file=sys.stderr,
            )
        return 1

    assert isinstance(outcome, ComplianceQuerySuccess)
    if as_json:
        print(json.dumps(_success_payload(outcome), indent=2, sort_keys=True))
    else:
        _print_human_success(outcome)
    return 0


def query(
    question: Annotated[str, typer.Argument(..., help="Natural language compliance question.")],
    regulation_id: Annotated[
        str | None,
        typer.Option(
            "--regulation-id",
            "-r",
            help="Optional regulation ID to scope the query.",
        ),
    ] = None,
    use_graph_rag: Annotated[
        bool,
        typer.Option(
            "--graph-rag/--no-graph-rag",
            help="Use GraphRAG (hybrid) vs vector-only retrieval (live mode).",
        ),
    ] = True,
    top_k: Annotated[
        int,
        typer.Option("--top-k", min=1, max=50, help="Number of chunks to retrieve."),
    ] = 10,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print JSON (success or service-unavailable body)."),
    ] = False,
) -> None:
    """Answer a compliance question using the same service as the HTTP API (no HTTP)."""
    code = asyncio.run(
        _query_async(
            question=question,
            regulation_id=regulation_id,
            use_graph_rag=use_graph_rag,
            top_k=top_k,
            as_json=as_json,
        )
    )
    raise typer.Exit(code)
