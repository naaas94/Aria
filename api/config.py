"""API layer configuration from environment."""

from __future__ import annotations

import os


def placeholder_api_enabled() -> bool:
    """When true, /impact and /query return synthetic data with ``X-ARIA-Mode: placeholder``."""
    return os.getenv("ARIA_PLACEHOLDER_API", "true").lower() in ("1", "true", "yes")


def strict_schema_version_expected() -> str | None:
    """If set, contract models reject mismatched ``schema_version`` (see ``aria.contracts._strict``)."""
    v = os.getenv("ARIA_STRICT_SCHEMA_VERSION", "").strip()
    return v or None


def cors_allow_origins() -> list[str]:
    """Parse ``CORS_ORIGINS`` or ``CORS_ALLOW_ORIGINS``: comma-separated list, or ``*`` for any origin."""
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if not raw:
        raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if not raw:
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ]
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


def is_production_deployment() -> bool:
    return os.getenv("DEPLOYMENT_ENV", "").strip().lower() in (
        "production",
        "prod",
    )
