"""GET /agents — A2A agent registry view."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from aria.protocols.a2a.agent_card import AGENT_CARDS

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
async def list_agents() -> list[dict[str, Any]]:
    """List all registered A2A agent cards."""
    return [card.model_dump() for card in AGENT_CARDS.values()]


@router.get("/{agent_name}")
async def get_agent(agent_name: str) -> dict[str, Any]:
    """Get a specific agent card by name."""
    card = AGENT_CARDS.get(agent_name)
    if not card:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    return card.model_dump()
