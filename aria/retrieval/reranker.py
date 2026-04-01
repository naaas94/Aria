"""Result scoring and merging logic for hybrid retrieval.

Combines vector similarity scores with graph context presence to
produce a unified ranking. Chunks that appear in both vector results
and graph neighborhoods receive a boost.
"""

from __future__ import annotations

from dataclasses import dataclass

from aria.retrieval.graph_retriever import GraphContext
from aria.retrieval.vector_store import RetrievedChunk

GRAPH_BOOST = 0.15
MIN_SCORE_THRESHOLD = 0.1


@dataclass
class RerankedResult:
    """A single result after fusion scoring."""

    chunk_id: str
    text: str
    score: float
    source: str  # "vector", "graph", or "both"


def rerank_results(
    vector_chunks: list[RetrievedChunk],
    graph_contexts: list[GraphContext],
    *,
    graph_boost: float = GRAPH_BOOST,
    max_results: int = 15,
) -> list[RerankedResult]:
    """Merge and rerank vector + graph results.

    Scoring:
    - Base score = vector similarity score
    - Boost applied if the chunk ID appears in graph expansion neighborhoods
    - Graph-only results get a fixed base score of 0.5
    """
    graph_node_ids: set[str] = set()
    graph_texts: dict[str, str] = {}
    for ctx in graph_contexts:
        graph_node_ids.add(ctx.anchor_id)
        for neighbor in ctx.neighbors:
            for key in ("id", "neighbor.id"):
                if nid := _extract_nested(neighbor, key):
                    graph_node_ids.add(str(nid))

    scored: dict[str, RerankedResult] = {}

    for chunk in vector_chunks:
        in_graph = chunk.chunk_id in graph_node_ids
        boost = graph_boost if in_graph else 0.0
        scored[chunk.chunk_id] = RerankedResult(
            chunk_id=chunk.chunk_id,
            text=chunk.text,
            score=chunk.score + boost,
            source="both" if in_graph else "vector",
        )

    for ctx in graph_contexts:
        if ctx.anchor_id not in scored:
            scored[ctx.anchor_id] = RerankedResult(
                chunk_id=ctx.anchor_id,
                text=ctx.context_text,
                score=0.5 + graph_boost,
                source="graph",
            )

    results = sorted(scored.values(), key=lambda r: r.score, reverse=True)
    return [r for r in results[:max_results] if r.score >= MIN_SCORE_THRESHOLD]


def _extract_nested(data: dict, dotted_key: str) -> object | None:
    keys = dotted_key.split(".")
    current: object = data
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return None
    return current
