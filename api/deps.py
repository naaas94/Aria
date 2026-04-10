"""Shared FastAPI dependencies (API key when configured)."""

from __future__ import annotations

import os

from fastapi import Header, HTTPException, status

from api.config import observability_public_while_api_key_configured


def _configured_api_key() -> str | None:
    return os.getenv("API_KEY") or os.getenv("ARIA_API_KEY") or None


def _api_key_matches(
    expected: str,
    x_api_key: str | None,
    authorization: str | None,
) -> bool:
    if x_api_key == expected:
        return True
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        if token == expected:
            return True
    return False


async def require_api_key_when_configured(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> None:
    """If ``API_KEY`` or ``ARIA_API_KEY`` is set, require it via header.

    Accepts ``X-API-Key: <key>`` or ``Authorization: Bearer <key>``.
    """
    expected = _configured_api_key()
    if not expected:
        return
    if _api_key_matches(expected, x_api_key, authorization):
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
    )


async def require_api_key_for_observability(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> None:
    """Gate ``/metrics`` and ``/telemetry`` when an API key is configured.

    Unless ``ARIA_OBSERVABILITY_PUBLIC=true``, uses the same key requirement as
    ``require_api_key_when_configured``.
    """
    expected = _configured_api_key()
    if not expected:
        return
    if observability_public_while_api_key_configured():
        return
    if _api_key_matches(expected, x_api_key, authorization):
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
    )
