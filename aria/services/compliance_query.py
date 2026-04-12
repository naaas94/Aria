"""Multi-hop compliance query (placeholder or live retrieval + LLM)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aria.graph.client import Neo4jClient
from aria.llm.client import LLMClient
from aria.observability.metrics import RETRIEVAL_COUNTER, RETRIEVAL_DURATION
from aria.retrieval.graph_retriever import GraphRetriever
from aria.retrieval.hybrid_retriever import HybridRetriever
from aria.retrieval.vector_store import VectorStore


class ComplianceQueryConnections(Protocol):
    """Minimal connection shape for :func:`run_compliance_query` (e.g. ``AppConnections``)."""

    neo4j: Neo4jClient | None
    vector_store: VectorStore | None


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


@dataclass(frozen=True)
class ComplianceQuerySuccess:
    """Successful query result (placeholder or live)."""

    response: ComplianceQueryResponse
    aria_mode: Literal["placeholder", "live"]


@dataclass(frozen=True)
class ComplianceQueryUnavailable:
    """Live mode requested but required backends are missing."""

    detail: str
    missing_dependencies: list[str]


ComplianceQueryOutcome = ComplianceQuerySuccess | ComplianceQueryUnavailable


async def run_compliance_query(
    request_dto: ComplianceQueryRequest,
    conns: ComplianceQueryConnections,
    *,
    use_placeholder: bool,
) -> ComplianceQueryOutcome:
    """Run a compliance question using GraphRAG or vector-only retrieval.

    When ``use_placeholder`` is true, returns synthetic content suitable for demos/tests.

    When false, requires Chroma for all live paths; GraphRAG also requires Neo4j.
    """
    strategy = "graphrag" if request_dto.use_graph_rag else "vector_only"

    if use_placeholder:
        return ComplianceQuerySuccess(
            response=ComplianceQueryResponse(
                answer=(
                    f"[Placeholder] Would answer: '{request_dto.question}' "
                    f"using {strategy} retrieval"
                    + (
                        f" scoped to {request_dto.regulation_id}"
                        if request_dto.regulation_id
                        else ""
                    )
                ),
                sources=[],
                retrieval_strategy=strategy,
                trace={
                    "top_k": request_dto.top_k,
                    "regulation_id": request_dto.regulation_id,
                },
            ),
            aria_mode="placeholder",
        )

    missing: list[str] = []
    if conns.vector_store is None:
        missing.append("chroma")
    if request_dto.use_graph_rag and conns.neo4j is None:
        missing.append("neo4j")

    if missing:
        return ComplianceQueryUnavailable(
            detail="Live query requires connected vector store (Chroma) "
            + ("and Neo4j for GraphRAG. " if request_dto.use_graph_rag else "")
            + "See /ready for checks.",
            missing_dependencies=missing,
        )

    llm = LLMClient()
    retrieval_start = time.monotonic()

    if request_dto.use_graph_rag:
        assert conns.neo4j is not None and conns.vector_store is not None
        graph_retriever = GraphRetriever(conns.neo4j)
        hybrid = HybridRetriever(
            conns.vector_store,
            graph_retriever,
            vector_top_k=request_dto.top_k,
            graph_hops=1,
        )
        result = await hybrid.retrieve(request_dto.question, node_label_hint="Article")
        RETRIEVAL_COUNTER.labels(strategy=strategy).inc()
        RETRIEVAL_DURATION.labels(strategy=strategy).observe(time.monotonic() - retrieval_start)
        context = result.context_text
        scope_line = (
            f"Regulation scope: {request_dto.regulation_id}\n\n"
            if request_dto.regulation_id
            else "\n\n"
        )
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
                    f"Question: {request_dto.question}\n"
                    f"{scope_line}"
                    f"Context:\n{context}"
                ),
            },
        ]
        answer = await llm.complete(messages)
        sources = [
            {"text": r.text, "score": r.score}
            for r in result.reranked[: min(10, request_dto.top_k)]
        ]
        if not sources and result.vector_chunks:
            sources = [
                {"text": c.text, "score": c.score}
                for c in result.vector_chunks[: min(10, request_dto.top_k)]
            ]
        trace = {
            **result.trace,
            "top_k": request_dto.top_k,
            "regulation_id": request_dto.regulation_id,
        }
        return ComplianceQuerySuccess(
            response=ComplianceQueryResponse(
                answer=answer,
                sources=sources,
                retrieval_strategy=strategy,
                trace=trace,
            ),
            aria_mode="live",
        )

    assert conns.vector_store is not None
    chunks = conns.vector_store.search(request_dto.question, top_k=request_dto.top_k)
    RETRIEVAL_COUNTER.labels(strategy=strategy).inc()
    RETRIEVAL_DURATION.labels(strategy=strategy).observe(time.monotonic() - retrieval_start)
    context = "\n\n".join(f"[{c.score:.3f}] {c.text}" for c in chunks)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a regulatory compliance assistant. Answer using the retrieved excerpts."
            ),
        },
        {
            "role": "user",
            "content": f"Question: {request_dto.question}\n\nExcerpts:\n{context}",
        },
    ]
    answer = await llm.complete(messages)
    sources = [{"text": c.text, "score": c.score} for c in chunks]
    trace = {
        "top_k": request_dto.top_k,
        "regulation_id": request_dto.regulation_id,
        "vector_chunk_count": len(chunks),
    }
    return ComplianceQuerySuccess(
        response=ComplianceQueryResponse(
            answer=answer,
            sources=sources,
            retrieval_strategy=strategy,
            trace=trace,
        ),
        aria_mode="live",
    )
