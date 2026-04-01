"""Inter-agent message envelope schemas.

Standardized message format for communication between agents, used by both
the scratch orchestration engine and the A2A protocol layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

SCHEMA_VERSION = "0.1.0"


class MessageType(StrEnum):
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    STATUS = "status"


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class AgentMessage(BaseModel):
    """Envelope for all inter-agent communication."""

    schema_version: str = SCHEMA_VERSION
    message_id: str = Field(default_factory=_uuid)
    timestamp: datetime = Field(default_factory=_now)
    message_type: MessageType
    source_agent: str
    target_agent: str
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = Field(
        default=None,
        description="Links request/response pairs and traces across agents",
    )


class TaskEnvelope(BaseModel):
    """Wrapper for delegated tasks — used by A2A and the orchestration engine."""

    task_id: str = Field(default_factory=_uuid)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    source_agent: str
    target_agent: str
    task_type: str = Field(..., description="Canonical task name (e.g. 'entity_extraction')")
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] = Field(default_factory=dict)
    error_detail: str | None = None

    def mark_in_progress(self) -> None:
        self.status = TaskStatus.IN_PROGRESS
        self.updated_at = _now()

    def mark_completed(self, output: dict[str, Any]) -> None:
        self.status = TaskStatus.COMPLETED
        self.output_payload = output
        self.updated_at = _now()

    def mark_failed(self, error: str) -> None:
        self.status = TaskStatus.FAILED
        self.error_detail = error
        self.updated_at = _now()
