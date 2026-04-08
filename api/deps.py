"""Shared FastAPI dependencies (API key when configured)."""

from __future__ import annotations

import os

from fastapi import Header, HTTPException, status


def _configured_api_key() -> str | None:
    return os.getenv("API_KEY") or os.getenv("ARIA_API_KEY") or None


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

    if x_api_key == expected:
        return
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        if token == expected:
            return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
    )
