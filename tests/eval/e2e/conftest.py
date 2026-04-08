"""Fixtures for E2E evaluation tests.

Provides an async HTTP client wired to the ASGI app and a unique
``eval_run_id`` that is propagated as ``X-Request-ID`` so every request
within a session shares a correlation prefix.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app


@pytest.fixture(scope="session")
def eval_run_id() -> str:
    """Unique run identifier shared by all E2E cases in a session."""
    return uuid.uuid4().hex[:12]


@pytest.fixture
async def e2e_client() -> AsyncClient:
    """Async HTTP client pointed at the ASGI app (no network required)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
