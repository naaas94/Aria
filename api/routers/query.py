"""POST /query — multi-hop compliance query."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/query", tags=["query"])


class ComplianceQueryRequest(BaseModel):
    question: str = Field(..., description="Natural language compliance question")
    regulation_id: str | None = Field(
        default=None, description="Optional regulation ID to scope the query"
    )
    use_graph_rag: bool = Field(
        default=True, description="Whether to use GraphRAG (hybrid) or vector-only retrieval"
    )
    top_k: int = Field(default=10, ge=1, le=50)


class ComplianceQueryResponse(BaseModel):
    answer: str = ""
    sources: list[dict[str, Any]] = []
    retrieval_strategy: str = "graphrag"
    trace: dict[str, Any] = {}


@router.post("", response_model=ComplianceQueryResponse)
async def compliance_query(request: ComplianceQueryRequest) -> ComplianceQueryResponse:
    """Answer a multi-hop compliance question using GraphRAG.

    This endpoint will:
    1. Embed the question via vector search
    2. Expand results through the knowledge graph
    3. Fuse and rerank results
    4. Generate an answer via LLM

    Currently returns a placeholder — full pipeline requires
    running Neo4j and ChromaDB services.
    """
    strategy = "graphrag" if request.use_graph_rag else "vector_only"

    return ComplianceQueryResponse(
        answer=(
            f"[Placeholder] Would answer: '{request.question}' "
            f"using {strategy} retrieval"
            + (f" scoped to {request.regulation_id}" if request.regulation_id else "")
        ),
        sources=[],
        retrieval_strategy=strategy,
        trace={"top_k": request.top_k, "regulation_id": request.regulation_id},
    )
