"""A2A client for outbound task delegation to peer agents.

Serializes a task, POSTs it to the peer agent's A2A endpoint,
awaits the response, and validates against the expected schema.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from aria.contracts.agent_messages import TaskEnvelope, TaskStatus
from aria.protocols.a2a.agent_card import AgentCard

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120.0


class A2AClient:
    """Client for delegating tasks to peer agents via A2A protocol."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._timeout = timeout

    async def delegate_task(
        self,
        target_card: AgentCard,
        task_type: str,
        input_payload: dict[str, Any],
        source_agent: str = "supervisor",
    ) -> TaskEnvelope:
        """Send a task to a peer agent and return the result envelope.

        Args:
            target_card: The A2A card of the target agent.
            task_type: Canonical task name (e.g. 'entity_extraction').
            input_payload: Task input data.
            source_agent: ID of the requesting agent.
        """
        if not target_card.endpoint:
            raise ValueError(f"Agent {target_card.name} has no A2A endpoint configured")

        envelope = TaskEnvelope(
            source_agent=source_agent,
            target_agent=target_card.agent_id,
            task_type=task_type,
            input_payload=input_payload,
        )

        logger.info(
            "Delegating task %s to %s at %s",
            envelope.task_id, target_card.name, target_card.endpoint,
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{target_card.endpoint}/tasks",
                    json=envelope.model_dump(mode="json"),
                )
                response.raise_for_status()
                result_data = response.json()
                result_envelope = TaskEnvelope.model_validate(result_data)
                logger.info(
                    "Task %s completed with status: %s",
                    envelope.task_id, result_envelope.status,
                )
                return result_envelope

        except httpx.HTTPStatusError as exc:
            envelope.mark_failed(f"HTTP {exc.response.status_code}: {exc.response.text}")
            return envelope

        except Exception as exc:
            envelope.mark_failed(f"Delegation failed: {exc}")
            logger.error("A2A delegation to %s failed: %s", target_card.name, exc)
            return envelope

    async def check_health(self, target_card: AgentCard) -> bool:
        """Check if a peer agent is reachable."""
        if not target_card.endpoint:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{target_card.endpoint}/health")
                return response.status_code == 200
        except Exception:
            return False
