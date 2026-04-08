"""Optional strict schema_version enforcement (ARIA_STRICT_SCHEMA_VERSION)."""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel


def strict_schema_version_expected() -> str | None:
    v = os.getenv("ARIA_STRICT_SCHEMA_VERSION", "").strip()
    return v or None


def enforce_schema_version_if_configured(instance: BaseModel, *, field: str = "schema_version") -> None:
    expected = strict_schema_version_expected()
    if not expected:
        return
    actual: Any = getattr(instance, field, None)
    if actual != expected:
        raise ValueError(
            f"{instance.__class__.__name__}.{field} must be {expected!r} when "
            f"ARIA_STRICT_SCHEMA_VERSION is set; got {actual!r}"
        )
