"""Impact report for a regulation in-process (same logic as ``GET /impact/{id}``).

Live mode (``ARIA_PLACEHOLDER_API=false``) requires Neo4j, matching the API. Align
``ARIA_PLACEHOLDER_API`` and ``NEO4J_*`` with the API process. Use ``aria status`` to
verify backends.
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
from aria.services.impact_report import (
    ImpactReportSuccess,
    ImpactReportUnavailable,
    ImpactSummaryResponse,
    run_impact_report,
)


def _print_human_success(response: ImpactSummaryResponse, aria_mode: str) -> None:
    print(f"Regulation: {response.regulation_id}")
    if response.regulation_title:
        print(f"Title: {response.regulation_title}")
    print(f"Mode: {aria_mode}")
    print(
        f"Requirements: {response.total_requirements} | "
        f"Affected systems: {response.affected_systems} | "
        f"Gaps: {response.gap_count} | Risk: {response.risk_level}"
    )
    if response.details:
        print()
        print("Details (first entries):")
        for row in response.details[:20]:
            print(f"  {row}")


def _success_payload(response: ImpactSummaryResponse, aria_mode: str) -> dict[str, Any]:
    return {
        **response.model_dump(mode="json"),
        "aria_mode": aria_mode,
    }


async def _impact_async(*, regulation_id: str, as_json: bool) -> int:
    use_placeholder = placeholder_api_enabled()
    if use_placeholder:
        conns = AppConnections()
        outcome = await run_impact_report(regulation_id, conns, use_placeholder=True)
    else:
        conns = await connect_app_dependencies(strict=True)
        try:
            outcome = await run_impact_report(regulation_id, conns, use_placeholder=False)
        finally:
            await disconnect_app_dependencies(conns)

    if isinstance(outcome, ImpactReportUnavailable):
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

    assert isinstance(outcome, ImpactReportSuccess)
    if as_json:
        payload = _success_payload(outcome.response, outcome.aria_mode)
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _print_human_success(outcome.response, outcome.aria_mode)
    return 0


def impact(
    regulation_id: Annotated[str, typer.Argument(..., help="Regulation identifier.")],
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print JSON (success or service-unavailable body)."),
    ] = False,
) -> None:
    """Summarize regulatory impact using the same service as the HTTP API (no HTTP)."""
    code = asyncio.run(_impact_async(regulation_id=regulation_id, as_json=as_json))
    raise typer.Exit(code)
