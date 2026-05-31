"""Orchestrated compliance query via scratch graph + MCP tool ports."""

from __future__ import annotations

from api.connections import AppConnections
from aria.orchestration.scratch.state import ARIAState
from aria.protocols.mcp.server import MCPServer, MCPToolPortsAdapter
from aria.services.compliance_query import (
    ComplianceQueryOutcome,
    ComplianceQueryRequest,
    ComplianceQueryResponse,
    ComplianceQuerySuccess,
    ComplianceQueryUnavailable,
)


def build_mcp_adapter(conns: AppConnections) -> MCPToolPortsAdapter:
    server = MCPServer(neo4j_client=conns.neo4j, vector_store=conns.vector_store)
    return MCPToolPortsAdapter(mcp_server=server)


async def run_orchestrated_query(
    request_dto: ComplianceQueryRequest,
    conns: AppConnections,
) -> ComplianceQueryOutcome:
    missing: list[str] = []
    if conns.neo4j is None:
        missing.append("neo4j")
    if conns.vector_store is None:
        missing.append("chroma")
    if missing:
        return ComplianceQueryUnavailable(
            detail="Orchestrated mode requires Neo4j and Chroma. See /ready for checks.",
            missing_dependencies=missing,
        )

    adapter = build_mcp_adapter(conns)
    state = ARIAState(
        query=request_dto.question,
        regulation_id=request_dto.regulation_id,
    )

    from aria.orchestration.scratch.graph import build_default_graph  # noqa: PLC0415

    graph = build_default_graph()
    result = await graph.execute(state, adapter)
    final = result.final_state

    if not result.success or final.error:
        return ComplianceQueryUnavailable(
            detail=final.error or "Orchestrated query failed",
            missing_dependencies=[],
        )

    answer = final.final_report or ""
    return ComplianceQuerySuccess(
        response=ComplianceQueryResponse(
            answer=answer,
            sources=[],
            retrieval_strategy="orchestrated",
            trace={},
            execution_trace=result.to_trace_dict(),
        ),
        aria_mode="live",
    )
