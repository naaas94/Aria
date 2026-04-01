"""BaseAgent abstract class with lifecycle hooks.

All ARIA agents inherit from this class, gaining a standard lifecycle
(initialize -> process -> finalize), structured logging, and a
reference to the shared tool ports.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class AgentResult(BaseModel):
    """Standard result envelope returned by all agents."""

    agent_name: str
    success: bool
    output: dict[str, Any] = {}
    error: str | None = None
    duration_ms: float = 0.0


class BaseAgent(ABC):
    """Abstract base for all ARIA agents."""

    name: str = "base_agent"

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"aria.agents.{self.name}")

    async def initialize(self) -> None:
        """Called once before processing. Override for setup logic."""
        self.logger.debug("%s initialized", self.name)

    @abstractmethod
    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Core processing logic. Must be implemented by subclasses."""
        ...

    async def finalize(self) -> None:
        """Called after processing completes. Override for cleanup."""
        self.logger.debug("%s finalized", self.name)

    async def run(self, input_data: dict[str, Any]) -> AgentResult:
        """Full lifecycle: initialize -> process -> finalize with timing."""
        start = time.monotonic()
        try:
            await self.initialize()
            output = await self.process(input_data)
            await self.finalize()
            return AgentResult(
                agent_name=self.name,
                success=True,
                output=output,
                duration_ms=(time.monotonic() - start) * 1000,
            )
        except Exception as exc:
            self.logger.exception("%s failed", self.name)
            return AgentResult(
                agent_name=self.name,
                success=False,
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
            )
