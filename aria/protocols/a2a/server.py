"""A2A server — lightweight FastAPI router for inbound task reception.

Each agent mounts this router to receive A2A task delegations.
The server validates incoming task envelopes, dispatches to the
agent's process method, and returns the result envelope.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Awaitable

from fastapi import APIRouter, Depends, Header, HTTPException, status

from aria.contracts.agent_messages import TaskEnvelope, TaskStatus
from aria.protocols.a2a.agent_card import AgentCard

logger = logging.getLogger(__name__)

TaskHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


async def verify_a2a_secret_when_configured(
    x_a2a_secret: str | None = Header(default=None, alias="X-A2A-Secret"),
) -> None:
    """Require ``X-A2A-Secret`` when ``A2A_SHARED_SECRET`` is set."""
    secret = os.getenv("A2A_SHARED_SECRET", "").strip()
    if not secret:
        return
    if x_a2a_secret != secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing A2A secret",
        )


class A2AServer:
    """A2A inbound task server that agents mount as a FastAPI router."""

    def __init__(self, agent_card: AgentCard, handler: TaskHandler) -> None:
        self._card = agent_card
        self._handler = handler
        self.router = APIRouter(prefix="/a2a", tags=["a2a"])
        if not os.getenv("A2A_SHARED_SECRET", "").strip():
            logger.warning(
                "A2A_SHARED_SECRET is not set — /a2a/card and /a2a/tasks are "
                "unauthenticated. Set A2A_SHARED_SECRET when agents are network-exposed.",
            )
        self._setup_routes()

    def _setup_routes(self) -> None:
        a2a_auth = [Depends(verify_a2a_secret_when_configured)]

        @self.router.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "healthy", "agent_id": self._card.agent_id}

        @self.router.get("/card", dependencies=a2a_auth)
        async def get_card() -> dict[str, Any]:
            return self._card.model_dump()

        @self.router.post("/tasks", dependencies=a2a_auth)
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
        except Exception:
            envelope.mark_failed(
                "Task execution failed. See server logs for details.",
            )
            logger.exception("Task %s failed", envelope.task_id)

        return envelope
