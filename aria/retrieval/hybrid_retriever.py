"""Fuses vector search and graph traversal results for GraphRAG retrieval.

The hybrid retriever implements the query phase of GraphRAG:
1. Vector search finds semantically similar chunks (anchor candidates)
2. Graph expansion pulls structured relational context from anchors
3. Fusion combines both signals into ranked context for the LLM
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from aria.retrieval.graph_retriever import GraphContext, GraphRetriever
from aria.retrieval.reranker import RerankedResult, rerank_results
from aria.retrieval.vector_store import RetrievedChunk, VectorStore

logger = logging.getLogger(__name__)


@dataclass
class HybridResult:
    """Combined retrieval result from vector + graph sources."""

    vector_chunks: list[RetrievedChunk] = field(default_factory=list)
    graph_contexts: list[GraphContext] = field(default_factory=list)
    reranked: list[RerankedResult] = field(default_factory=list)

    @property
    def context_text(self) -> str:
        """Build a unified context string for LLM consumption."""
        parts: list[str] = []

        if self.reranked:
            parts.append("=== Relevant Context (ranked) ===")
            for r in self.reranked:
                parts.append(f"[score={r.score:.3f}] {r.text}")
        else:
            if self.vector_chunks:
                parts.append("=== Vector Search Results ===")
                for chunk in self.vector_chunks:
                    parts.append(f"[similarity={chunk.score:.3f}] {chunk.text}")

            if self.graph_contexts:
                parts.append("\n=== Graph Context ===")
                for ctx in self.graph_contexts:
                    parts.append(ctx.context_text)

        return "\n\n".join(parts)

    @property
    def trace(self) -> dict[str, Any]:
        """Structured trace for evaluation and debugging."""
        return {
            "vector_chunk_count": len(self.vector_chunks),
            "graph_context_count": len(self.graph_contexts),
            "reranked_count": len(self.reranked),
            "vector_scores": [c.score for c in self.vector_chunks],
            "reranked_scores": [r.score for r in self.reranked],
        }


class HybridRetriever:
    """Orchestrates vector search + graph expansion + result fusion."""

    def __init__(
        self,
        vector_store: VectorStore,
        graph_retriever: GraphRetriever,
        *,
        vector_top_k: int = 10,
        graph_hops: int = 1,
        graph_limit: int = 25,
    ) -> None:
        self._vector_store = vector_store
        self._graph_retriever = graph_retriever
        self._vector_top_k = vector_top_k
        self._graph_hops = graph_hops
        self._graph_limit = graph_limit

    async def retrieve(
        self,
        query: str,
        *,
        vector_top_k: int | None = None,
        graph_hops: int | None = None,
        node_label_hint: str = "Article",
    ) -> HybridResult:
        """Run hybrid retrieval: vector search -> graph expansion -> fusion.

        Args:
            query: The user's compliance question.
            vector_top_k: Override default vector result count.
            graph_hops: Override default graph expansion depth (1 or 2).
            node_label_hint: Expected label of anchor nodes for graph expansion.
        """
        top_k = vector_top_k or self._vector_top_k
        hops = graph_hops or self._graph_hops

        vector_chunks = self._vector_store.search(query, top_k=top_k)
        logger.info("Vector search returned %d chunks for query", len(vector_chunks))

        graph_contexts: list[GraphContext] = []
        for chunk in vector_chunks[:5]:
            node_id = chunk.metadata.get("node_id", chunk.chunk_id)
            try:
                if hops == 1:
                    ctx = await self._graph_retriever.expand_one_hop(
                        node_id, node_label_hint, limit=self._graph_limit
                    )
                else:
                    ctx = await self._graph_retriever.expand_two_hops(
                        node_id, node_label_hint, limit=self._graph_limit
                    )
                if ctx.neighbors or ctx.paths:
                    graph_contexts.append(ctx)
            except Exception:
                logger.debug("Graph expansion failed for anchor %s", node_id, exc_info=True)

        reranked = rerank_results(vector_chunks, graph_contexts)

        result = HybridResult(
            vector_chunks=vector_chunks,
            graph_contexts=graph_contexts,
            reranked=reranked,
        )
        logger.info(
            "Hybrid retrieval complete: %d vector, %d graph, %d reranked",
            len(vector_chunks), len(graph_contexts), len(reranked),
        )
        return result
