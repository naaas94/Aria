"""LangGraph state definition — uses the same ARIAState as the scratch engine.

This module re-exports the canonical ARIAState from the scratch implementation
to guarantee parity. The only addition is the TypedDict adapter that LangGraph
expects for its StateGraph API.
"""

from __future__ import annotations

from typing import Any, TypedDict

from aria.orchestration.scratch.state import ARIAState


class ARIAStateDict(TypedDict, total=False):
    """TypedDict adapter for LangGraph's StateGraph.

    LangGraph uses TypedDict for state channels. This maps 1:1
    to the Pydantic ARIAState from the scratch implementation.
    """

    regulation_id: str | None
    raw_document: str | None
    document_hash: str | None
    query: str | None
    extracted_entities: dict[str, Any] | None
    graph_write_status: dict[str, Any] | None
    impact_report: dict[str, Any] | None
    final_report: str | None
    error: str | None
    current_node: str
    history: list[str]


def pydantic_to_dict(state: ARIAState) -> ARIAStateDict:
    """Convert Pydantic ARIAState to TypedDict for LangGraph."""
    data = state.model_dump()
    return ARIAStateDict(**data)


def dict_to_pydantic(state_dict: dict[str, Any]) -> ARIAState:
    """Convert LangGraph state dict back to Pydantic ARIAState."""
    return ARIAState.model_validate(state_dict)
