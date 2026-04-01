"""A2A server — lightweight FastAPI router for inbound task reception.

Each agent mounts this router to receive A2A task delegations.
The server validates incoming task envelopes, dispatches to the
agent's process method, and returns the result envelope.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from fastapi import APIRouter, HTTPException

from aria.contracts.agent_messages import TaskEnvelope, TaskStatus
from aria.protocols.a2a.agent_card import AgentCard

logger = logging.getLogger(__name__)

TaskHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class A2AServer:
    """A2A inbound task server that agents mount as a FastAPI router."""

    def __init__(self, agent_card: AgentCard, handler: TaskHandler) -> None:
        self._card = agent_card
        self._handler = handler
        self.router = APIRouter(prefix="/a2a", tags=["a2a"])
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.router.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "healthy", "agent_id": self._card.agent_id}

        @self.router.get("/card")
        async def get_card() -> dict[str, Any]:
            return self._card.model_dump()

        @self.router.post("/tasks")
        async def receive_task(envelope: TaskEnvelope) -> TaskEnvelope:
            return await self._process_task(envelope)

    async def _process_task(self, envelope: TaskEnvelope) -> TaskEnvelope:
        logger.info(
            "Received A2A task %s (type=%s) from %s",
            envelope.task_id, envelope.task_type, envelope.source_agent,
        )

        envelope.mark_in_progress()

        try:
            output = await self._handler(envelope.input_payload)
            envelope.mark_completed(output)
            logger.info("Task %s completed successfully", envelope.task_id)
        except Exception as exc:
            envelope.mark_failed(str(exc))
            logger.error("Task %s failed: %s", envelope.task_id, exc)

        return envelope
