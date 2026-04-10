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


def telemetry_retention_days() -> int | None:
    """If set to a positive integer, the API process prunes telemetry older than N days (UTC).

    Unset or invalid values disable automatic in-process retention (use an external job or cron).
    """
    raw = os.getenv("ARIA_TELEMETRY_RETENTION_DAYS", "").strip()
    if not raw:
        return None
    try:
        n = int(raw)
    except ValueError:
        return None
    return n if n > 0 else None


def telemetry_prune_interval_seconds() -> int:
    """Sleep interval between automatic telemetry prunes when retention is enabled (minimum 60s)."""
    raw = os.getenv("ARIA_TELEMETRY_PRUNE_INTERVAL_SECONDS", "86400").strip()
    try:
        return max(60, int(raw))
    except ValueError:
        return 86400


def observability_public_while_api_key_configured() -> bool:
    """When true, ``GET /metrics`` and ``GET /telemetry`` skip API key checks.

    Default is false: if ``API_KEY`` / ``ARIA_API_KEY`` is set, observability routes
    require the same key as the rest of the API. Set this only for internal networks
    where Prometheus scrapes ``/metrics`` without auth (accept reconnaissance exposure).
    """
    return os.getenv("ARIA_OBSERVABILITY_PUBLIC", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
