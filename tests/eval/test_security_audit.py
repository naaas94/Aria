"""Executable security audit checks for the ARIA GraphRAG agent stack.

These tests assert safe defaults (parameterized Cypher, generic MCP/A2A errors),
optional controls (API key, A2A secret), and document residual risk.

Run: pytest tests/eval/test_security_audit.py -v -m security
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.main import app
from aria.contracts.agent_messages import TaskEnvelope, TaskStatus
from tests.eval.expected_api_paths import EXPECTED_OPENAPI_PATHS
from aria.protocols.a2a.client import A2AClient
from aria.graph.queries import QUERIES, execute_named_query
from aria.llm.client import LLMClient
from aria.protocols.a2a.agent_card import AgentCard
from aria.protocols.a2a.server import A2AServer
from aria.protocols.mcp.server import MCPServer


pytestmark = pytest.mark.security

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Authentication & authorization
# ---------------------------------------------------------------------------


def _collect_api_paths_methods() -> list[tuple[str, str]]:
    """Return (method, path) for the main FastAPI app (OpenAPI paths)."""
    schema = app.openapi()
    out: list[tuple[str, str]] = []
    for path, item in schema.get("paths", {}).items():
        for method in item:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
                out.append((method.upper(), path))
    return sorted(out)


def test_main_api_routes_work_without_credentials_when_api_key_unset() -> None:
    """When ``API_KEY`` is unset, data-plane routes accept unauthenticated requests."""
    client = TestClient(app)
    for method, path in _collect_api_paths_methods():
        if "{" in path:
            path = path.replace("{regulation_id}", "reg-test").replace("{agent_name}", "entity_extractor")
        kwargs: dict[str, Any] = {}
        if method == "GET":
            r = client.get(path)
        elif method == "POST":
            if path == "/ingest/text":
                kwargs["json"] = {"text": "audit probe", "source": "security_test"}
            elif path == "/ingest/file":
                continue
            elif path == "/query":
                kwargs["json"] = {"question": "audit probe", "use_graph_rag": True, "top_k": 3}
            else:
                kwargs["json"] = {}
            r = client.post(path, **kwargs)
        else:
            continue
        assert r.status_code != 401, f"{method} {path} unexpectedly required auth"
        assert r.status_code != 403, f"{method} {path} unexpectedly forbidden without credentials"


def test_rest_routes_require_api_key_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "test-secret-key")
    monkeypatch.delenv("ARIA_OBSERVABILITY_PUBLIC", raising=False)
    client = TestClient(app)
    r = client.get("/agents")
    assert r.status_code == 401
    r2 = client.get("/agents", headers={"X-API-Key": "test-secret-key"})
    assert r2.status_code == 200


def test_observability_routes_require_api_key_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_KEY", "test-secret-key")
    monkeypatch.delenv("ARIA_OBSERVABILITY_PUBLIC", raising=False)
    client = TestClient(app)
    assert client.get("/metrics").status_code == 401
    assert client.get("/telemetry").status_code == 401
    headers = {"X-API-Key": "test-secret-key"}
    assert client.get("/metrics", headers=headers).status_code == 200
    assert client.get("/telemetry", headers=headers).status_code == 200


def test_observability_routes_public_flag_bypasses_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_KEY", "test-secret-key")
    monkeypatch.setenv("ARIA_OBSERVABILITY_PUBLIC", "true")
    client = TestClient(app)
    assert client.get("/metrics").status_code == 200
    assert client.get("/telemetry").status_code == 200


def test_health_and_ready_skip_api_key_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "test-secret-key")
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    ready = client.get("/ready")
    assert ready.status_code in (200, 503)
    body = ready.json()
    assert "llm" in body
    assert body.get("llm") in (True, False)


def test_ingest_file_accepts_upload_when_api_key_unset() -> None:
    client = TestClient(app)
    r = client.post(
        "/ingest/file",
        files={"file": ("probe.txt", b"security audit content", "text/plain")},
    )
    assert r.status_code != 401
    assert r.status_code in (200, 400, 422)


def test_documented_openapi_paths_match_expected_set() -> None:
    paths = {p for _, p in _collect_api_paths_methods()}
    assert EXPECTED_OPENAPI_PATHS == paths, (
        "OpenAPI path set changed: update tests/eval/expected_api_paths.py and "
        "expected_paths in tests/eval/golden_set/cases/security/openapi_paths.yaml.\n"
        f"OpenAPI paths: {sorted(paths)}"
    )


def test_golden_openapi_paths_yaml_matches_ssot() -> None:
    yaml_path = (
        REPO_ROOT
        / "tests"
        / "eval"
        / "golden_set"
        / "cases"
        / "security"
        / "openapi_paths.yaml"
    )
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    listed = set(raw["input"]["expected_paths"])
    assert listed == EXPECTED_OPENAPI_PATHS, (
        "openapi_paths.yaml expected_paths must match tests/eval/expected_api_paths.py"
    )


def test_a2a_tasks_accept_requests_when_shared_secret_unset() -> None:
    calls: list[dict[str, Any]] = []

    async def handler(payload: dict[str, Any]) -> dict[str, Any]:
        calls.append(payload)
        return {"ok": True}

    card = AgentCard(
        agent_id="audit-agent",
        name="audit",
        description="test",
        version="0",
        capabilities=[],
        endpoint="http://localhost:9999/a2a",
    )
    a2a = A2AServer(card, handler)
    sub = FastAPI()
    sub.include_router(a2a.router)
    client = TestClient(sub)

    env = TaskEnvelope(
        source_agent="ext",
        target_agent="audit",
        task_type="anything_goes",
        input_payload={"probe": True},
    )
    r = client.post("/a2a/tasks", json=env.model_dump(mode="json"))
    assert r.status_code == 200, r.text
    assert calls == [{"probe": True}]


def test_a2a_tasks_require_secret_header_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A2A_SHARED_SECRET", "super-sekrit")

    async def handler(payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    card = AgentCard(
        agent_id="audit-agent",
        name="audit",
        description="test",
        version="0",
        capabilities=[],
        endpoint="http://localhost:9999/a2a",
    )
    a2a = A2AServer(card, handler)
    sub = FastAPI()
    sub.include_router(a2a.router)
    client = TestClient(sub)

    env = TaskEnvelope(
        source_agent="ext",
        target_agent="audit",
        task_type="t",
        input_payload={},
    )
    bad = client.post("/a2a/tasks", json=env.model_dump(mode="json"))
    assert bad.status_code == 401
    good = client.post(
        "/a2a/tasks",
        json=env.model_dump(mode="json"),
        headers={"X-A2A-Secret": "super-sekrit"},
    )
    assert good.status_code == 200


@pytest.mark.asyncio
async def test_a2a_client_delegate_task_401_without_secret_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the peer requires ``X-A2A-Secret``, outbound requests without it get HTTP 401."""
    monkeypatch.setenv("A2A_SHARED_SECRET", "peer-secret")

    async def handler(payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    card = AgentCard(
        agent_id="peer",
        name="peer",
        description="t",
        version="0",
        capabilities=[],
        endpoint="http://test/a2a",
    )
    a2a = A2AServer(card, handler)
    sub = FastAPI()
    sub.include_router(a2a.router)

    transport = httpx.ASGITransport(app=sub)

    class _PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = transport
            kwargs["base_url"] = "http://test"
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("aria.protocols.a2a.client.httpx.AsyncClient", _PatchedAsyncClient)
    monkeypatch.setattr("aria.protocols.a2a.client._a2a_shared_secret_from_env", lambda: "")

    a2a_client = A2AClient()
    out = await a2a_client.delegate_task(
        card,
        task_type="t",
        input_payload={},
        source_agent="caller",
    )
    assert out.status == TaskStatus.FAILED
    assert out.error_detail is not None
    assert "401" in out.error_detail


@pytest.mark.asyncio
async def test_a2a_client_delegate_task_200_with_secret_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``A2AClient`` sends ``X-A2A-Secret`` when ``A2A_SHARED_SECRET`` is set."""
    monkeypatch.setenv("A2A_SHARED_SECRET", "peer-secret")

    async def handler(payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    card = AgentCard(
        agent_id="peer",
        name="peer",
        description="t",
        version="0",
        capabilities=[],
        endpoint="http://test/a2a",
    )
    a2a = A2AServer(card, handler)
    sub = FastAPI()
    sub.include_router(a2a.router)

    transport = httpx.ASGITransport(app=sub)

    class _PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = transport
            kwargs["base_url"] = "http://test"
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("aria.protocols.a2a.client.httpx.AsyncClient", _PatchedAsyncClient)

    a2a_client = A2AClient()
    out = await a2a_client.delegate_task(
        card,
        task_type="t",
        input_payload={},
        source_agent="caller",
    )
    assert out.status == TaskStatus.COMPLETED
    assert out.output_payload == {"ok": True}


def test_api_package_has_no_bearer_or_oauth_dependencies() -> None:
    for path in (REPO_ROOT / "api").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "HTTPBearer" not in text, f"Unexpected bearer auth in {path}"
        assert "OAuth2PasswordBearer" not in text, f"Unexpected OAuth2 in {path}"


# ---------------------------------------------------------------------------
# Injection: Cypher (named-query surface)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("query_name", sorted(QUERIES.keys()))
def test_named_query_cypher_templates_are_not_built_from_user_strings(query_name: str) -> None:
    q = QUERIES[query_name]
    malicious = "'; MATCH (z) DETACH DELETE z //"
    params: dict[str, Any] = {name: malicious for name in q.parameter_names}
    if not params:
        pytest.skip("parameterless query")
    cypher, bound = execute_named_query(query_name, params)
    assert cypher == q.cypher
    for k, v in bound.items():
        assert v == malicious


def test_unknown_query_name_cannot_select_alternate_cypher() -> None:
    with pytest.raises(KeyError, match="Unknown query"):
        execute_named_query("'; DROP INDEX * //", {"regulation_id": "x"})


# ---------------------------------------------------------------------------
# Information disclosure: errors and logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_tool_errors_are_generic_with_stable_code() -> None:
    mcp = MCPServer(neo4j_client=None, vector_store=None)

    async def boom(_: dict[str, Any]) -> Any:
        raise ValueError("internal_secret_graph_connection_id=xyzzy")

    mcp._handlers["graph_query"] = boom  # type: ignore[method-assign]

    result = await mcp.call_tool(
        "graph_query", {"query_name": "list_regulations", "parameters": {}}
    )
    assert result.success is False
    assert result.error is not None
    assert "internal_secret" not in result.error
    assert result.error_code == "MCP_TOOL_EXECUTION_FAILED"


@pytest.mark.asyncio
async def test_mcp_unknown_tool_returns_generic_error_code() -> None:
    mcp = MCPServer(neo4j_client=None, vector_store=None)
    result = await mcp.call_tool("nonexistent_tool", {})
    assert result.success is False
    assert result.error_code == "MCP_UNKNOWN_TOOL"


@pytest.mark.asyncio
async def test_a2a_failed_task_envelope_hides_exception_details() -> None:
    async def bad(_: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("neo4j://user:pass@internal-host:7687 leaked")

    card = AgentCard(
        agent_id="x",
        name="x",
        description="x",
        version="0",
        capabilities=[],
        endpoint="http://localhost/a2a",
    )
    server = A2AServer(card, bad)
    env = TaskEnvelope(
        source_agent="a",
        target_agent="x",
        task_type="t",
        input_payload={},
    )
    out = await server._process_task(env)
    assert out.status == TaskStatus.FAILED
    assert out.error_detail is not None
    assert "internal-host" not in out.error_detail
    assert "server logs" in out.error_detail.lower()


def test_uvicorn_dockerfile_does_not_enable_reload_debug() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "--reload" not in dockerfile


# ---------------------------------------------------------------------------
# Configuration security
# ---------------------------------------------------------------------------


def test_docker_compose_neo4j_auth_documents_dev_default_password() -> None:
    text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "aria_dev_password" in text


def test_seed_script_neo4j_password_default_matches_compose_dev_secret() -> None:
    text = (REPO_ROOT / "scripts" / "seed_graph.py").read_text(encoding="utf-8")
    assert 'os.getenv("NEO4J_PASSWORD", "aria_dev_password")' in text


def test_llm_client_default_api_key_is_placeholder_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    client = LLMClient()
    assert client.api_key == "not-needed"


def test_llm_client_rejects_placeholder_key_for_non_local_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        LLMClient()


def test_cors_default_origins_are_localhost_dev_urls() -> None:
    from api import main as api_main

    mw = [x for x in api_main.app.user_middleware if x.cls.__name__ == "CORSMiddleware"]
    assert len(mw) == 1
    origins = mw[0].kwargs.get("allow_origins") or []
    assert "http://localhost:3000" in origins
    assert "http://127.0.0.1:3000" in origins


def test_cors_allow_origins_env_supports_wildcard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "*")
    from api.config import cors_allow_origins

    assert cors_allow_origins() == ["*"]


# ---------------------------------------------------------------------------
# Supply chain
# ---------------------------------------------------------------------------


def test_pyproject_uses_lower_bound_dependencies() -> None:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    dep_block = re.search(r"dependencies = \[(.*?)\]", text, re.DOTALL)
    assert dep_block is not None
    block = dep_block.group(1)
    assert re.search(r'"\w[\w-]*==', block) is None, "some deps appear exact-pinned"
    assert ">=" in block


def test_uv_lockfile_committed() -> None:
    assert (REPO_ROOT / "uv.lock").is_file()


def test_chromadb_image_is_pinned_not_latest() -> None:
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "chromadb/chroma:latest" not in compose
    assert re.search(r"chromadb/chroma:[\w.]+", compose) is not None


# ---------------------------------------------------------------------------
# Data handling: upload and prompt paths
# ---------------------------------------------------------------------------


def test_ingest_file_route_enforces_max_bytes_after_read() -> None:
    from api.routers import ingest as ingest_router

    src = inspect.getsource(ingest_router.ingest_file)
    assert "INGEST_MAX_BYTES" in src or "_ingest_max_bytes" in src
    assert "len(content)" in src


def test_entity_extractor_interpolates_document_text_into_user_prompt() -> None:
    from aria.agents.entity_extractor import EntityExtractorAgent
    from aria.llm.prompts import entity_extraction as prompts

    src = inspect.getsource(EntityExtractorAgent.process)
    assert "ENTITY_EXTRACTION_USER" in src or "format(document_text" in src
    assert "<<<DOCUMENT>>>" in prompts.ENTITY_EXTRACTION_USER
    assert "untrusted" in prompts.ENTITY_EXTRACTION_SYSTEM.lower()
