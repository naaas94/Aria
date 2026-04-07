"""Uniform HTTP error bodies for API responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    """Stable JSON shape for non-2xx API errors (aligns with extended HTTPException usage)."""

    detail: str
    code: str = Field(default="error", description="Machine-readable error category")


class ServiceUnavailableBody(BaseModel):
    """Returned when live mode requires dependencies that are not connected."""

    detail: str
    code: str = "service_unavailable"
    missing_dependencies: list[str] = Field(default_factory=list)


def validation_error_payload(errors: list[dict[str, Any]]) -> dict[str, Any]:
    """Body for 422 validation errors (same envelope as ErrorBody + FastAPI detail list)."""
    return {
        "detail": errors,
        "code": "validation_error",
    }
