"""POST /query — multi-hop compliance query (placeholder or live)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.config import placeholder_api_enabled
from api.connections import get_app_connections
from api.errors import ServiceUnavailableBody
from aria.llm.client import LLMClient
from aria.retrieval.graph_retriever import GraphRetriever
from aria.retrieval.hybrid_retriever import HybridRetriever

router = APIRouter(prefix="/query", tags=["query"])


class ComplianceQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., description="Natural language compliance question")
    regulation_id: str | None = Field(
        default=None, description="Optional regulation ID to scope the query"
    )
    use_graph_rag: bool = Field(
        default=True, description="Whether to use GraphRAG (hybrid) or vector-only retrieval"
    )
    top_k: int = Field(default=10, ge=1, le=50)

    @field_validator("regulation_id", mode="before")
    @classmethod
    def regulation_id_empty_to_none(cls, v: object) -> object:
        if v == "":
            return None
        return v


class ComplianceQueryResponse(BaseModel):
    answer: str = ""
    sources: list[dict[str, Any]] = []
    retrieval_strategy: str = "graphrag"
    trace: dict[str, Any] = {}


@router.post(
    "",
    response_model=ComplianceQueryResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ServiceUnavailableBody,
            "description": "Live mode without required Neo4j/Chroma (ARIA_PLACEHOLDER_API=false).",
        },
    },
)
async def compliance_query(
    query_request: ComplianceQueryRequest,
    request: Request,
    response: Response,
) -> ComplianceQueryResponse | JSONResponse:
    """Answer a compliance question using GraphRAG or vector-only retrieval.

    With ``ARIA_PLACEHOLDER_API=true`` (default), returns a documented placeholder
    and ``X-ARIA-Mode: placeholder``.

    With ``ARIA_PLACEHOLDER_API=false``, runs hybrid or vector retrieval plus an LLM.
    Requires Chroma for all live paths; GraphRAG also requires Neo4j.
    """
    conns = get_app_connections(request)
    strategy = "graphrag" if query_request.use_graph_rag else "vector_only"

    if placeholder_api_enabled():
        response.headers["X-ARIA-Mode"] = "placeholder"
        return ComplianceQueryResponse(
            answer=(
                f"[Placeholder] Would answer: '{query_request.question}' "
                f"using {strategy} retrieval"
                + (f" scoped to {query_request.regulation_id}" if query_request.regulation_id else "")
            ),
            sources=[],
            retrieval_strategy=strategy,
            trace={"top_k": query_request.top_k, "regulation_id": query_request.regulation_id},
        )

    missing: list[str] = []
    if conns.vector_store is None:
        missing.append("chroma")
    if query_request.use_graph_rag and conns.neo4j is None:
        missing.append("neo4j")

    if missing:
        svc = ServiceUnavailableBody(
            detail="Live query requires connected vector store (Chroma) "
            + ("and Neo4j for GraphRAG. " if query_request.use_graph_rag else "")
            + "See /ready for checks.",
            missing_dependencies=missing,
        )
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=svc.model_dump())

    response.headers["X-ARIA-Mode"] = "live"
    llm = LLMClient()

    if query_request.use_graph_rag:
        assert conns.neo4j is not None and conns.vector_store is not None
        graph_retriever = GraphRetriever(conns.neo4j)
        hybrid = HybridRetriever(
            conns.vector_store,
            graph_retriever,
            vector_top_k=query_request.top_k,
            graph_hops=1,
        )
        result = await hybrid.retrieve(query_request.question, node_label_hint="Article")
        context = result.context_text
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a regulatory compliance assistant. Answer concisely using "
                    "only the provided context when possible."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question: {query_request.question}\n"
                    f"{('Regulation scope: ' + query_request.regulation_id) if query_request.regulation_id else ''}\n\n"
                    f"Context:\n{context}"
                ),
            },
        ]
        answer = await llm.complete(messages)
        sources = [
            {"text": r.text, "score": r.score}
            for r in result.reranked[: min(10, query_request.top_k)]
        ]
        if not sources and result.vector_chunks:
            sources = [
                {"text": c.text, "score": c.score}
                for c in result.vector_chunks[: min(10, query_request.top_k)]
            ]
        trace = {
            **result.trace,
            "top_k": query_request.top_k,
            "regulation_id": query_request.regulation_id,
        }
        return ComplianceQueryResponse(
            answer=answer,
            sources=sources,
            retrieval_strategy=strategy,
            trace=trace,
        )

    assert conns.vector_store is not None
    chunks = conns.vector_store.search(query_request.question, top_k=query_request.top_k)
    context = "\n\n".join(f"[{c.score:.3f}] {c.text}" for c in chunks)
    messages = [
        {
            "role": "system",
            "content": "You are a regulatory compliance assistant. Answer using the retrieved excerpts.",
        },
        {
            "role": "user",
            "content": f"Question: {query_request.question}\n\nExcerpts:\n{context}",
        },
    ]
    answer = await llm.complete(messages)
    sources = [{"text": c.text, "score": c.score} for c in chunks]
    trace = {
        "top_k": query_request.top_k,
        "regulation_id": query_request.regulation_id,
        "vector_chunk_count": len(chunks),
    }
    return ComplianceQueryResponse(
        answer=answer,
        sources=sources,
        retrieval_strategy=strategy,
        trace=trace,
    )
