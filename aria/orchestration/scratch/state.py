"""Typed shared state object for the scratch orchestration engine.

ARIAState is the canonical state contract — both the scratch engine and
the LangGraph reference implementation operate on this exact schema.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from aria.contracts.graph_entities import GraphWriteStatus
from aria.contracts.impact import ImpactReport
from aria.contracts.regulation import ExtractedEntities


class ARIAState(BaseModel):
    """Shared mutable state flowing through the orchestration graph.

    Each node receives the current state, performs its work, and returns
    an updated copy. The engine advances based on edge routing decisions.
    """

    regulation_id: str | None = None
    raw_document: str | None = None
    document_hash: str | None = None
    query: str | None = None

    extracted_entities: ExtractedEntities | None = None
    graph_write_status: GraphWriteStatus | None = None
    impact_report: ImpactReport | None = None
    final_report: str | None = None

    error: str | None = None
    current_node: str = "supervisor"
    history: list[str] = Field(default_factory=list)

    def record_step(self, node_name: str) -> None:
        self.history.append(node_name)
        self.current_node = node_name

    @property
    def has_error(self) -> bool:
        return self.error is not None

    @property
    def is_ingestion_request(self) -> bool:
        return self.raw_document is not None

    @property
    def is_impact_query(self) -> bool:
        return self.regulation_id is not None and self.raw_document is None

    @property
    def is_free_query(self) -> bool:
        return self.query is not None and self.regulation_id is None and self.raw_document is None
