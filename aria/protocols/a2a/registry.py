"""Local agent card registry — in-memory + file-persisted discovery.

Agents register their cards on startup and query the registry to
discover peers with matching capabilities.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from aria.protocols.a2a.agent_card import AgentCard

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY_PATH = Path("agent_registry.json")


class AgentRegistry:
    """In-memory registry with optional file persistence."""

    def __init__(self, persist_path: Path | None = None) -> None:
        self._cards: dict[str, AgentCard] = {}
        self._persist_path = persist_path or DEFAULT_REGISTRY_PATH

    def register(self, card: AgentCard) -> None:
        """Register or update an agent card."""
        self._cards[card.agent_id] = card
        logger.info("Registered agent: %s (%s)", card.name, card.agent_id)

    def deregister(self, agent_id: str) -> bool:
        """Remove an agent card. Returns True if the agent was found."""
        if agent_id in self._cards:
            del self._cards[agent_id]
            logger.info("Deregistered agent: %s", agent_id)
            return True
        return False

    def get(self, agent_id: str) -> AgentCard | None:
        return self._cards.get(agent_id)

    def list_all(self) -> list[AgentCard]:
        return list(self._cards.values())

    def find_by_capability(self, capability: str) -> list[AgentCard]:
        """Find all agents that advertise a specific capability."""
        return [c for c in self._cards.values() if c.supports_capability(capability)]

    def find_by_name(self, name: str) -> AgentCard | None:
        for card in self._cards.values():
            if card.name == name:
                return card
        return None

    def save(self) -> None:
        """Persist the registry to a JSON file."""
        data = {aid: card.model_dump() for aid, card in self._cards.items()}
        self._persist_path.write_text(json.dumps(data, indent=2, default=str))
        logger.info("Registry saved to %s (%d agents)", self._persist_path, len(data))

    def load(self) -> None:
        """Load the registry from a JSON file."""
        if not self._persist_path.exists():
            logger.info("No registry file found at %s", self._persist_path)
            return

        data: dict[str, Any] = json.loads(self._persist_path.read_text())
        for agent_id, card_data in data.items():
            self._cards[agent_id] = AgentCard.model_validate(card_data)
        logger.info("Registry loaded from %s (%d agents)", self._persist_path, len(data))

    @property
    def count(self) -> int:
        return len(self._cards)
