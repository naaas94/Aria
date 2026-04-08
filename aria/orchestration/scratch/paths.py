"""Canonical node sequences for the default scratch orchestration graph.

Single source of truth for evals, fixtures, and documentation. Keep in sync
with ``build_default_graph`` in ``graph.py`` and ``EDGE_MAP`` in ``edges.py``.
"""

from __future__ import annotations

SCRATCH_END = "end"

# Ingestion pipeline (supervisor → ingestion validates doc → entity_extractor → graph_builder …)
CANONICAL_SCRATCH_INGESTION_PATH_NO_REG: list[str] = [
    "supervisor",
    "ingestion",
    "entity_extractor",
    "graph_builder",
    SCRATCH_END,
]

CANONICAL_SCRATCH_INGESTION_PATH_WITH_REG: list[str] = [
    "supervisor",
    "ingestion",
    "entity_extractor",
    "graph_builder",
    "impact_analyzer",
    "report_generator",
    SCRATCH_END,
]

CANONICAL_SCRATCH_IMPACT_QUERY_PATH: list[str] = [
    "supervisor",
    "impact_analyzer",
    "report_generator",
    SCRATCH_END,
]

CANONICAL_SCRATCH_FREE_QUERY_PATH: list[str] = [
    "supervisor",
    "free_query",
    SCRATCH_END,
]

CANONICAL_SCRATCH_UNKNOWN_PATH: list[str] = [
    "supervisor",
    SCRATCH_END,
]
