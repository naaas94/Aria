"""E2E query tests against the real ARIA API.

Each test sends ``POST /query`` through the ASGI app and validates:
  - HTTP contract (status, response shape)
  - Retrieval metadata (strategy, sources, trace fields)
  - Output quality (keyword presence, answer bounds)

By default the app runs in placeholder mode (``ARIA_PLACEHOLDER_API=true``)
which exercises serialization, routing, and middleware without external deps.
In nightly CI the env is set to ``false`` with live Neo4j + Chroma so the
same tests exercise the full hybrid/vector retrieval path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from httpx import AsyncClient

from api.routers.query import ComplianceQueryResponse


@dataclass
class E2ECase:
    """Declarative E2E test case."""

    id: str
    question: str
    use_graph_rag: bool = True
    top_k: int = 10
    regulation_id: str | None = None
    expected_strategy: str = "graphrag"
    expected_source_keywords: list[str] = field(default_factory=list)
    min_sources: int = 0
    must_mention: list[str] = field(default_factory=list)
    must_not_mention: list[str] = field(default_factory=list)
    max_answer_length: int = 5000


E2E_CASES = [
    E2ECase(
        id="e2e-graphrag-gdpr-dpia",
        question="Which systems need a data protection impact assessment under GDPR Article 35?",
        use_graph_rag=True,
        expected_strategy="graphrag",
        expected_source_keywords=["article 35", "impact assessment"],
        must_mention=["35"],
    ),
    E2ECase(
        id="e2e-graphrag-ai-act-transparency",
        question="What transparency obligations does the EU AI Act impose on AI systems?",
        use_graph_rag=True,
        expected_strategy="graphrag",
        expected_source_keywords=["article 52", "transparency"],
        must_mention=["transparency"],
    ),
    E2ECase(
        id="e2e-vector-only-erasure",
        question="What is the right to erasure under GDPR?",
        use_graph_rag=False,
        expected_strategy="vector_only",
        expected_source_keywords=["erasure", "right to be forgotten"],
        must_mention=["erasure"],
    ),
    E2ECase(
        id="e2e-graphrag-cross-regulation",
        question="Which teams are affected by both GDPR and EU AI Act requirements?",
        use_graph_rag=True,
        expected_strategy="graphrag",
    ),
    E2ECase(
        id="e2e-vector-scoped",
        question="List all requirements from the EU AI Act",
        use_graph_rag=False,
        regulation_id="reg-eu-ai-act",
        expected_strategy="vector_only",
        must_mention=["AI"],
    ),
]


def _build_correlation_id(eval_run_id: str, case_id: str) -> str:
    return f"{eval_run_id}:{case_id}"


@pytest.mark.eval
@pytest.mark.integration
@pytest.mark.parametrize("case", E2E_CASES, ids=lambda c: c.id)
async def test_e2e_query(
    case: E2ECase,
    e2e_client: AsyncClient,
    eval_run_id: str,
) -> None:
    correlation_id = _build_correlation_id(eval_run_id, case.id)

    payload = {
        "question": case.question,
        "use_graph_rag": case.use_graph_rag,
        "top_k": case.top_k,
    }
    if case.regulation_id is not None:
        payload["regulation_id"] = case.regulation_id

    resp = await e2e_client.post(
        "/query",
        json=payload,
        headers={"X-Request-ID": correlation_id},
    )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    returned_request_id = resp.headers.get("x-request-id")
    assert returned_request_id == correlation_id, (
        f"Correlation ID mismatch: sent {correlation_id!r}, got {returned_request_id!r}"
    )

    body = resp.json()
    parsed = ComplianceQueryResponse.model_validate(body)

    assert parsed.retrieval_strategy == case.expected_strategy, (
        f"Strategy mismatch: expected {case.expected_strategy}, got {parsed.retrieval_strategy}"
    )

    assert isinstance(parsed.answer, str) and len(parsed.answer) > 0, "Empty answer"
    assert len(parsed.answer) <= case.max_answer_length, (
        f"Answer too long: {len(parsed.answer)} > {case.max_answer_length}"
    )

    assert isinstance(parsed.trace, dict), "Trace should be a dict"
    assert "top_k" in parsed.trace, "Trace missing top_k"

    answer_lower = parsed.answer.lower()
    for kw in case.must_mention:
        assert kw.lower() in answer_lower, f"Answer must mention '{kw}'"
    for kw in case.must_not_mention:
        assert kw.lower() not in answer_lower, f"Answer must NOT mention '{kw}'"

    is_live = resp.headers.get("x-aria-mode") == "live"
    if is_live:
        assert len(parsed.sources) >= case.min_sources, (
            f"Live mode: expected >= {case.min_sources} sources, got {len(parsed.sources)}"
        )
        for src_kw in case.expected_source_keywords:
            source_text = " ".join(s.get("text", "") for s in parsed.sources).lower()
            assert src_kw.lower() in source_text, (
                f"Live mode: expected source keyword '{src_kw}' not found"
            )
