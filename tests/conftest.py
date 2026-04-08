"""Pytest defaults — keep HTTP tests independent of developer .env API keys.

Session-scoped ``TestClient`` runs FastAPI lifespan so ``app.state.connections`` exists.
Async eval tests use the ``http_client`` fixture (httpx + ASGI) against the same app.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from api.main import app


@pytest.fixture(autouse=True)
def _clear_api_key_env_for_http_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unless a test sets ``API_KEY``/``ARIA_API_KEY``, callers should not get 401 from the app."""
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("ARIA_API_KEY", raising=False)


@pytest.fixture(scope="session", autouse=True)
def _keep_app_lifespan_active() -> None:
    with TestClient(app):
        yield


@pytest.fixture
async def http_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
