"""Per-lens check functions for golden-set evaluation.

Each ``run_*_check`` function accepts a :class:`GoldenCase` and returns a
:class:`CheckOutcome`.  The driver calls whichever lenses are present in
``case.expect``.
"""

from __future__ import annotations

import importlib
import re
import time
from dataclasses import dataclass, field
from typing import Any

from .schema import GoldenCase


@dataclass
class CheckOutcome:
    """Result of a single lens check on a golden case."""

    passed: bool
    detail: str = ""
    duration_ms: float = 0.0
    sub_checks: dict[str, bool] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Contract lens
# ---------------------------------------------------------------------------


def _import_model(dotted_path: str) -> type:
    module_path, _, cls_name = dotted_path.rpartition(".")
    mod = importlib.import_module(module_path)
    return getattr(mod, cls_name)


def run_contract_check(case: GoldenCase) -> CheckOutcome:
    """Validate data against a Pydantic model referenced by dotted path."""
    t0 = time.perf_counter()
    spec = case.expect.contract
    assert spec is not None

    model_cls = _import_model(spec.model)
    data = spec.fixture_data if spec.fixture_data is not None else case.input
    issues: list[str] = []
    sub: dict[str, bool] = {}

    try:
        instance = model_cls.model_validate(data)
        sub["validates"] = True
    except Exception as exc:
        sub["validates"] = False
        issues.append(f"Validation failed: {exc}")
        return CheckOutcome(
            passed=False,
            detail="; ".join(issues),
            duration_ms=(time.perf_counter() - t0) * 1000,
            sub_checks=sub,
        )

    for fld in spec.required_fields:
        present = hasattr(instance, fld) and getattr(instance, fld) is not None
        sub[f"field:{fld}"] = present
        if not present:
            issues.append(f"Missing required field: {fld}")

    if spec.schema_version is not None:
        actual = getattr(instance, "schema_version", None)
        sub["schema_version"] = actual == spec.schema_version
        if actual != spec.schema_version:
            issues.append(f"schema_version {actual!r} != expected {spec.schema_version!r}")

    passed = all(sub.values())
    return CheckOutcome(
        passed=passed,
        detail="; ".join(issues) if issues else "ok",
        duration_ms=(time.perf_counter() - t0) * 1000,
        sub_checks=sub,
    )


# ---------------------------------------------------------------------------
# Trace lens
# ---------------------------------------------------------------------------


def run_trace_check(case: GoldenCase) -> CheckOutcome:
    """Evaluate an orchestration trace embedded in ``case.input``."""
    t0 = time.perf_counter()
    spec = case.expect.trace
    assert spec is not None

    steps: list[dict[str, Any]] = case.input.get("steps", [])
    node_seq = [s.get("node_name", "") for s in steps]
    all_tools: list[str] = []
    has_error = False
    for s in steps:
        all_tools.extend(s.get("tool_calls", []))
        if s.get("error"):
            has_error = True

    issues: list[str] = []
    sub: dict[str, bool] = {}

    if spec.expected_sequence:
        match = node_seq == spec.expected_sequence
        sub["sequence"] = match
        if not match:
            issues.append(f"Expected sequence {spec.expected_sequence}, got {node_seq}")

    if spec.forbidden_nodes:
        forbidden_found = [n for n in node_seq if n in spec.forbidden_nodes]
        sub["no_forbidden_nodes"] = len(forbidden_found) == 0
        if forbidden_found:
            issues.append(f"Forbidden nodes present: {forbidden_found}")

    if spec.max_steps is not None:
        ok = len(steps) <= spec.max_steps
        sub["max_steps"] = ok
        if not ok:
            issues.append(f"Step count {len(steps)} exceeds max {spec.max_steps}")

    if spec.required_tools:
        for tool in spec.required_tools:
            present = tool in all_tools
            sub[f"tool:{tool}"] = present
            if not present:
                issues.append(f"Required tool missing: {tool}")

    if spec.forbidden_tools:
        for tool in spec.forbidden_tools:
            found = tool in all_tools
            sub[f"no_tool:{tool}"] = not found
            if found:
                issues.append(f"Forbidden tool present: {tool}")

    if spec.must_have_error:
        sub["has_error"] = has_error
        if not has_error:
            issues.append("Expected error in trace but none found")

    if spec.must_not_have_error:
        sub["no_error"] = not has_error
        if has_error:
            issues.append("Unexpected error in trace")

    passed = all(sub.values()) if sub else True
    return CheckOutcome(
        passed=passed,
        detail="; ".join(issues) if issues else "ok",
        duration_ms=(time.perf_counter() - t0) * 1000,
        sub_checks=sub,
    )


# ---------------------------------------------------------------------------
# Retrieval lens
# ---------------------------------------------------------------------------

DEFAULT_COMPONENT_KEYWORDS: dict[str, list[str]] = {
    "system_name": ["crm", "ml risk", "hr platform", "chatbot"],
    "requirement_text": ["shall", "must", "require", "obligation"],
    "team_name": ["engineering", "legal", "data science", "human resources"],
    "gap_status": ["gap", "uncovered", "no policy", "not addressed"],
    "deadline_date": ["2025", "2026", "deadline"],
    "article_number": [
        "article 5", "article 6", "article 9",
        "article 17", "article 35", "article 52",
    ],
    "regulation_title": ["gdpr", "ai act", "data protection", "artificial intelligence"],
    "article_text": ["erasure", "right to be forgotten", "personal data"],
    "data_types": ["personal_data", "financial_data", "biometric", "employee"],
}


def run_retrieval_check(case: GoldenCase) -> CheckOutcome:
    """Score retrieved context against expected components using keyword matching."""
    t0 = time.perf_counter()
    spec = case.expect.retrieval
    assert spec is not None

    context = case.input.get("retrieved_context", "").lower()
    keywords = {**DEFAULT_COMPONENT_KEYWORDS, **spec.component_keywords}

    sub: dict[str, bool] = {}
    issues: list[str] = []

    for component in spec.expected_components:
        kws = keywords.get(component, [])
        hit = any(kw in context for kw in kws) if kws else False
        sub[f"component:{component}"] = hit
        if not hit:
            issues.append(f"Component '{component}' not found in context")

    if spec.requires_multi_hop:
        sub["multi_hop_declared"] = True

    passed = all(sub.values()) if sub else True
    return CheckOutcome(
        passed=passed,
        detail="; ".join(issues) if issues else "ok",
        duration_ms=(time.perf_counter() - t0) * 1000,
        sub_checks=sub,
    )


# ---------------------------------------------------------------------------
# Security lens
# ---------------------------------------------------------------------------


def run_security_check(case: GoldenCase) -> CheckOutcome:
    """Run deterministic security assertions (status codes, string containment)."""
    t0 = time.perf_counter()
    spec = case.expect.security
    assert spec is not None

    issues: list[str] = []
    sub: dict[str, bool] = {}

    if spec.check_type:
        sub["check_type_defined"] = True
        return _run_named_security_check(case, t0)

    response_body: str = case.input.get("response_body", "")
    status_code: int | None = case.input.get("status_code")

    if spec.expected_status is not None and status_code is not None:
        ok = status_code == spec.expected_status
        sub["status_code"] = ok
        if not ok:
            issues.append(f"Expected status {spec.expected_status}, got {status_code}")

    for pattern in spec.must_not_contain:
        found = pattern.lower() in response_body.lower()
        sub[f"absent:{pattern}"] = not found
        if found:
            issues.append(f"Response must not contain '{pattern}'")

    for pattern in spec.must_contain:
        found = pattern.lower() in response_body.lower()
        sub[f"present:{pattern}"] = found
        if not found:
            issues.append(f"Response must contain '{pattern}'")

    passed = all(sub.values()) if sub else True
    return CheckOutcome(
        passed=passed,
        detail="; ".join(issues) if issues else "ok",
        duration_ms=(time.perf_counter() - t0) * 1000,
        sub_checks=sub,
    )


def _run_named_security_check(case: GoldenCase, t0: float) -> CheckOutcome:
    """Dispatch to a named security check that may do live probing."""
    spec = case.expect.security
    assert spec is not None
    name = spec.check_type or ""

    handlers: dict[str, Any] = {
        "cypher_parameterized": _check_cypher_parameterized,
        "mcp_error_generic": _check_mcp_error_generic,
        "no_reload_in_dockerfile": _check_no_reload_in_dockerfile,
        "openapi_paths": _check_openapi_paths,
        "unauthenticated_access": _check_unauthenticated_access,
        "api_key_enforcement": _check_api_key_enforcement,
        "a2a_secret_enforcement": _check_a2a_secret_enforcement,
        "supply_chain_lower_bounds": _check_supply_chain_lower_bounds,
    }

    handler = handlers.get(name)
    if handler is None:
        return CheckOutcome(
            passed=False,
            detail=f"Unknown security check_type: {name}",
            duration_ms=(time.perf_counter() - t0) * 1000,
        )

    return handler(case, t0)


def _check_cypher_parameterized(case: GoldenCase, t0: float) -> CheckOutcome:
    from aria.graph.queries import QUERIES, execute_named_query

    issues: list[str] = []
    sub: dict[str, bool] = {}
    malicious = "'; MATCH (z) DETACH DELETE z //"

    for qname, q in QUERIES.items():
        if not q.parameter_names:
            continue
        params = {n: malicious for n in q.parameter_names}
        cypher, bound = execute_named_query(qname, params)
        ok = cypher == q.cypher
        sub[f"query:{qname}"] = ok
        if not ok:
            issues.append(f"Query '{qname}' template was mutated by user input")

    return CheckOutcome(
        passed=all(sub.values()) if sub else True,
        detail="; ".join(issues) if issues else "ok",
        duration_ms=(time.perf_counter() - t0) * 1000,
        sub_checks=sub,
    )


def _check_mcp_error_generic(case: GoldenCase, t0: float) -> CheckOutcome:
    import asyncio

    from aria.protocols.mcp.server import MCPServer

    sub: dict[str, bool] = {}
    issues: list[str] = []

    mcp = MCPServer(neo4j_client=None, vector_store=None)

    async def _probe() -> None:
        result = await mcp.call_tool("nonexistent_tool", {})
        sub["unknown_tool_error"] = (
            result.success is False and result.error_code == "MCP_UNKNOWN_TOOL"
        )
        if not sub["unknown_tool_error"]:
            issues.append("Unknown tool did not return MCP_UNKNOWN_TOOL")

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            pool.submit(asyncio.run, _probe()).result()
    else:
        asyncio.run(_probe())

    return CheckOutcome(
        passed=all(sub.values()),
        detail="; ".join(issues) if issues else "ok",
        duration_ms=(time.perf_counter() - t0) * 1000,
        sub_checks=sub,
    )


def _check_no_reload_in_dockerfile(case: GoldenCase, t0: float) -> CheckOutcome:
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    dockerfile = repo_root / "Dockerfile"
    sub: dict[str, bool] = {}

    if dockerfile.exists():
        text = dockerfile.read_text(encoding="utf-8")
        sub["no_reload"] = "--reload" not in text
    else:
        sub["no_reload"] = True

    return CheckOutcome(
        passed=all(sub.values()),
        detail="ok" if all(sub.values()) else "--reload found in Dockerfile",
        duration_ms=(time.perf_counter() - t0) * 1000,
        sub_checks=sub,
    )


def _check_openapi_paths(case: GoldenCase, t0: float) -> CheckOutcome:
    from api.main import app

    schema = app.openapi()
    paths = set(schema.get("paths", {}).keys())
    expected = set(case.input.get("expected_paths", []))
    sub: dict[str, bool] = {"paths_match": paths == expected}
    detail = "ok" if sub["paths_match"] else f"Expected {sorted(expected)}, got {sorted(paths)}"

    return CheckOutcome(
        passed=sub["paths_match"],
        detail=detail,
        duration_ms=(time.perf_counter() - t0) * 1000,
        sub_checks=sub,
    )


def _check_unauthenticated_access(case: GoldenCase, t0: float) -> CheckOutcome:
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    path = case.input.get("path", "/health")
    method = case.input.get("method", "GET")
    sub: dict[str, bool] = {}

    if method == "GET":
        r = client.get(path)
    else:
        r = client.post(path, json=case.input.get("json_body", {}))

    sub["no_401"] = r.status_code != 401
    sub["no_403"] = r.status_code != 403

    issues = []
    if not sub["no_401"]:
        issues.append(f"{method} {path} unexpectedly required auth")
    if not sub["no_403"]:
        issues.append(f"{method} {path} unexpectedly forbidden")

    return CheckOutcome(
        passed=all(sub.values()),
        detail="; ".join(issues) if issues else "ok",
        duration_ms=(time.perf_counter() - t0) * 1000,
        sub_checks=sub,
    )


def _check_api_key_enforcement(case: GoldenCase, t0: float) -> CheckOutcome:
    import os

    from fastapi.testclient import TestClient

    from api.main import app

    sub: dict[str, bool] = {}
    issues: list[str] = []

    old_key = os.environ.get("API_KEY")
    try:
        os.environ["API_KEY"] = "test-golden-key"
        client = TestClient(app)

        r_no_key = client.get("/agents")
        sub["rejects_without_key"] = r_no_key.status_code == 401
        if not sub["rejects_without_key"]:
            issues.append(f"Expected 401 without key, got {r_no_key.status_code}")

        r_with_key = client.get("/agents", headers={"X-API-Key": "test-golden-key"})
        sub["accepts_with_key"] = r_with_key.status_code == 200
        if not sub["accepts_with_key"]:
            issues.append(f"Expected 200 with key, got {r_with_key.status_code}")

        r_health = client.get("/health")
        sub["health_bypasses"] = r_health.status_code == 200
        if not sub["health_bypasses"]:
            issues.append("Health endpoint did not bypass API key")
    finally:
        if old_key is not None:
            os.environ["API_KEY"] = old_key
        else:
            os.environ.pop("API_KEY", None)

    return CheckOutcome(
        passed=all(sub.values()),
        detail="; ".join(issues) if issues else "ok",
        duration_ms=(time.perf_counter() - t0) * 1000,
        sub_checks=sub,
    )


def _check_a2a_secret_enforcement(case: GoldenCase, t0: float) -> CheckOutcome:
    import asyncio
    import os

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from aria.contracts.agent_messages import TaskEnvelope
    from aria.protocols.a2a.agent_card import AgentCard
    from aria.protocols.a2a.server import A2AServer

    sub: dict[str, bool] = {}
    issues: list[str] = []

    old_secret = os.environ.get("A2A_SHARED_SECRET")
    try:
        os.environ["A2A_SHARED_SECRET"] = "golden-secret"

        async def handler(payload: dict[str, Any]) -> dict[str, Any]:
            return {"ok": True}

        card = AgentCard(
            agent_id="golden-agent",
            name="golden",
            description="test",
            version="0",
            capabilities=[],
            endpoint="http://localhost:9999/a2a",
        )
        a2a = A2AServer(card, handler)
        sub_app = FastAPI()
        sub_app.include_router(a2a.router)
        client = TestClient(sub_app)

        env = TaskEnvelope(
            source_agent="ext",
            target_agent="golden",
            task_type="t",
            input_payload={},
        )
        r_bad = client.post("/a2a/tasks", json=env.model_dump(mode="json"))
        sub["rejects_without_secret"] = r_bad.status_code == 401
        if not sub["rejects_without_secret"]:
            issues.append(f"Expected 401 without secret, got {r_bad.status_code}")

        r_good = client.post(
            "/a2a/tasks",
            json=env.model_dump(mode="json"),
            headers={"X-A2A-Secret": "golden-secret"},
        )
        sub["accepts_with_secret"] = r_good.status_code == 200
        if not sub["accepts_with_secret"]:
            issues.append(f"Expected 200 with secret, got {r_good.status_code}")
    finally:
        if old_secret is not None:
            os.environ["A2A_SHARED_SECRET"] = old_secret
        else:
            os.environ.pop("A2A_SHARED_SECRET", None)

    return CheckOutcome(
        passed=all(sub.values()),
        detail="; ".join(issues) if issues else "ok",
        duration_ms=(time.perf_counter() - t0) * 1000,
        sub_checks=sub,
    )


def _check_supply_chain_lower_bounds(case: GoldenCase, t0: float) -> CheckOutcome:
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")

    sub: dict[str, bool] = {}
    dep_block = re.search(r"dependencies = \[(.*?)\]", text, re.DOTALL)
    if dep_block:
        block = dep_block.group(1)
        sub["no_exact_pins"] = re.search(r'"\w[\w-]*==', block) is None
        sub["has_lower_bounds"] = ">=" in block
    else:
        sub["dep_block_found"] = False

    lockfile = repo_root / "uv.lock"
    sub["lockfile_exists"] = lockfile.is_file()

    issues = [k for k, v in sub.items() if not v]
    return CheckOutcome(
        passed=all(sub.values()),
        detail="; ".join(issues) if issues else "ok",
        duration_ms=(time.perf_counter() - t0) * 1000,
        sub_checks=sub,
    )


# ---------------------------------------------------------------------------
# Quality lens
# ---------------------------------------------------------------------------


def run_quality_check(case: GoldenCase) -> CheckOutcome:
    """Assess output quality of an LLM-generated answer.

    Works on both live responses (stored in ``case.input``) and replay
    fixtures.  Checks are deterministic: keyword presence, source count,
    answer length, and optional regex.
    """
    t0 = time.perf_counter()
    spec = case.expect.quality
    assert spec is not None

    answer: str = case.input.get("answer", "")
    sources: list[dict[str, Any]] = case.input.get("sources", [])
    answer_lower = answer.lower()

    issues: list[str] = []
    sub: dict[str, bool] = {}

    for kw in spec.must_mention:
        hit = kw.lower() in answer_lower
        sub[f"mentions:{kw}"] = hit
        if not hit:
            issues.append(f"Answer must mention '{kw}'")

    for kw in spec.must_not_mention:
        found = kw.lower() in answer_lower
        sub[f"absent:{kw}"] = not found
        if found:
            issues.append(f"Answer must NOT mention '{kw}'")

    if spec.min_source_count > 0:
        ok = len(sources) >= spec.min_source_count
        sub["min_sources"] = ok
        if not ok:
            issues.append(
                f"Expected >= {spec.min_source_count} sources, got {len(sources)}"
            )

    if spec.max_answer_length is not None:
        ok = len(answer) <= spec.max_answer_length
        sub["max_length"] = ok
        if not ok:
            issues.append(
                f"Answer length {len(answer)} exceeds max {spec.max_answer_length}"
            )

    if spec.answer_regex is not None:
        matched = re.search(spec.answer_regex, answer, re.IGNORECASE) is not None
        sub["regex_match"] = matched
        if not matched:
            issues.append(f"Answer does not match pattern '{spec.answer_regex}'")

    passed = all(sub.values()) if sub else True
    return CheckOutcome(
        passed=passed,
        detail="; ".join(issues) if issues else "ok",
        duration_ms=(time.perf_counter() - t0) * 1000,
        sub_checks=sub,
    )


# ---------------------------------------------------------------------------
# Replay lens
# ---------------------------------------------------------------------------


def run_replay_check(case: GoldenCase) -> CheckOutcome:
    """Validate a recorded replay fixture for contract and regression.

    Loads the fixture from ``replay/``, checks response shape, strategy,
    source count, required trace keys, and optionally runs quality sub-checks.
    """
    from .recorder import load_replay_fixture

    t0 = time.perf_counter()
    spec = case.expect.replay
    assert spec is not None

    issues: list[str] = []
    sub: dict[str, bool] = {}

    try:
        fixture = load_replay_fixture(spec.fixture_file)
    except FileNotFoundError as exc:
        return CheckOutcome(
            passed=False,
            detail=str(exc),
            duration_ms=(time.perf_counter() - t0) * 1000,
            sub_checks={"fixture_exists": False},
        )

    sub["fixture_exists"] = True
    resp = fixture.response

    sub["has_answer"] = bool(resp.get("answer"))
    if not sub["has_answer"]:
        issues.append("Replay fixture has no answer")

    if spec.expected_strategy is not None:
        actual = resp.get("retrieval_strategy", fixture.strategy_used)
        ok = actual == spec.expected_strategy
        sub["strategy_match"] = ok
        if not ok:
            issues.append(
                f"Strategy mismatch: expected {spec.expected_strategy}, got {actual}"
            )

    sources = resp.get("sources", [])
    if spec.min_source_count > 0:
        ok = len(sources) >= spec.min_source_count
        sub["min_sources"] = ok
        if not ok:
            issues.append(
                f"Expected >= {spec.min_source_count} sources, got {len(sources)}"
            )

    trace = resp.get("trace", {})
    for key in spec.required_trace_keys:
        present = key in trace
        sub[f"trace_key:{key}"] = present
        if not present:
            issues.append(f"Trace missing required key '{key}'")

    if spec.quality is not None:
        from .schema import GoldenCase as _GC, Expectations

        quality_case = _GC(
            id=case.id,
            category=case.category,
            tier=case.tier,
            input={"answer": resp.get("answer", ""), "sources": sources},
            expect=Expectations(quality=spec.quality),
        )
        q_outcome = run_quality_check(quality_case)
        for k, v in q_outcome.sub_checks.items():
            sub[f"quality:{k}"] = v
        if not q_outcome.passed:
            issues.append(f"Quality: {q_outcome.detail}")

    passed = all(sub.values()) if sub else True
    return CheckOutcome(
        passed=passed,
        detail="; ".join(issues) if issues else "ok",
        duration_ms=(time.perf_counter() - t0) * 1000,
        sub_checks=sub,
    )
