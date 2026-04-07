"""GET /agents — A2A agent registry view (backed by startup AgentRegistry)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from api.connections import get_app_connections
from aria.protocols.a2a.agent_card import AGENT_CARDS

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
async def list_agents(request: Request) -> list[dict[str, Any]]:
    """List all registered A2A agent cards (same source as ``AGENT_CARDS``, mirrored at startup)."""
    reg = get_app_connections(request).agent_registry
    cards = sorted(reg.list_all(), key=lambda c: c.agent_id)
    return [c.model_dump() for c in cards]


@router.get("/{agent_name}")
async def get_agent(agent_name: str, request: Request) -> dict[str, Any]:
    """Get a specific agent card by registry slug (e.g. ``supervisor``, ``entity_extractor``)."""
    slug_card = AGENT_CARDS.get(agent_name)
    if not slug_card:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    reg = get_app_connections(request).agent_registry
    card = reg.get(slug_card.agent_id)
    if card is None:
        raise HTTPException(
            status_code=503,
            detail="Agent registry not initialized — server misconfiguration",
        )
    return card.model_dump()
