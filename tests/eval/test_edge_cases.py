"""Boundary, malformed-input, and robustness checks across ingestion, contracts,
orchestration, LLM parsing, and the HTTP API.

Run: pytest tests/eval/test_edge_cases.py -v --tb=short
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from pydantic import BaseModel, ValidationError

from aria.contracts.graph_entities import GraphWritePayload
from aria.contracts.impact import CoverageStatus, ImpactReport, RiskLevel
from aria.contracts.regulation import ExtractedEntities, ObligationType, Regulation, Requirement
from aria.ingestion.chunker import chunk_text
from aria.llm.client import LLMClient
from aria.orchestration.scratch.edges import route_after_supervisor
from aria.orchestration.scratch.graph import OrchestrationGraph
from aria.orchestration.scratch.nodes import ToolPorts, ingestion_node, supervisor_node
from aria.orchestration.scratch.state import ARIAState

from tests.fixtures.graph_payloads import ADV_DUPLICATE_NODE_IDS_SAME_LABEL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _TinyStructured(BaseModel):
    """Minimal schema for LLM structured-output parsing tests."""

    answer: str
    score: int = 0


class _StubTools:
    """Minimal ToolPorts implementation for state-machine tests."""

    async def extract_entities(self, text: str, doc_hash: str) -> dict[str, Any]:
        return ExtractedEntities(
            source_document_hash=doc_hash or "unknown",
            regulations=[],
        ).model_dump()

    async def write_to_graph(self, entities: dict[str, Any]) -> dict[str, Any]:
        return {
            "nodes_created": 0,
            "nodes_merged": 0,
            "edges_created": 0,
            "edges_merged": 0,
            "errors": [],
        }

    async def index_vectors(self, chunks: list[dict[str, Any]]) -> bool:
        return True

    async def query_graph(self, query_name: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    async def vector_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        return []

    async def generate_text(self, messages: list[dict[str, str]]) -> str:
        return "ok"


# ---------------------------------------------------------------------------
# Input boundaries — document text & ingestion
# ---------------------------------------------------------------------------


@pytest.mark.eval
class TestInputBoundariesIngestion:
    """Chunking and size/encoding behavior for regulatory text prior to embedding."""

    def test_empty_document_yields_no_chunks(self):
        """What: ``chunk_text`` on empty / whitespace-only sentence split.
        Why: Avoids infinite loops and clarifies downstream empty-chunk handling.
        Expected: No chunks (no sentences)."""
        chunks = chunk_text("", source_hash="abc", metadata={})
        assert chunks == []

    def test_very_long_text_produces_many_chunks_without_crash(self):
        """What: ~120k characters of repetitive sentence text.
        Why: OOM or quadratic blowups should not occur on large paste-ins.
        Expected: Non-empty chunk list; total text largely preserved across chunks."""
        sentence = (
            "The controller shall document processing activities under Article 30. "
        )
        # Many sentences so chunker has boundaries (not one giant "sentence").
        text = (sentence * 800)[:120_000]
        chunks = chunk_text(text, source_hash="long-doc", metadata={"source": "test"})
        assert len(chunks) >= 1
        joined = " ".join(c.text for c in chunks)
        assert len(joined) > 50_000

    def test_unicode_rtl_emoji_and_zero_width_round_trip(self):
        """What: RTL marks, emoji, and zero-width joiner in document text.
        Why: Users paste mixed scripts; chunking must not strip or crash silently.
        Expected: Chunks retain characters; chunk_id is stable."""
        text = (
            "\u202bRegulation\u202c mixed with \U0001f9ea and "
            "zero\u200dwidth\u200djoiner inside a word."
        )
        chunks = chunk_text(text, source_hash="unicode", metadata={})
        assert len(chunks) >= 1
        assert "\U0001f9ea" in chunks[0].text
        assert "\u200d" in chunks[0].text

    def test_null_byte_in_text_does_not_break_chunker(self):
        """What: U+0000 inside a string (distinct from C NULL in C extensions).
        Why: Binary-tainted paste-ins should not take down the chunking path.
        Expected: Chunker returns; content still present in output."""
        text = "Before\x00After. Second sentence here."
        chunks = chunk_text(text, source_hash="null", metadata={})
        assert len(chunks) >= 1
        assert "\x00" in chunks[0].text


# ---------------------------------------------------------------------------
# Input boundaries — API ingest & query strings
# ---------------------------------------------------------------------------


@pytest.mark.eval
class TestInputBoundariesAPIIngest:
    """HTTP-layer validation for `/ingest/text` (empty body, encoding)."""

    @pytest.mark.asyncio
    async def test_empty_text_returns_400(self, http_client: AsyncClient):
        """What: JSON body with empty or whitespace-only `text`.
        Why: Prevents useless work and ambiguous hashes.
        Expected: 400 from explicit guard in router."""
        r = await http_client.post("/ingest/text", json={"text": ""})
        assert r.status_code == 400
        r2 = await http_client.post("/ingest/text", json={"text": "   \n\t  "})
        assert r2.status_code == 400

    @pytest.mark.asyncio
    async def test_null_text_field_returns_422(self, http_client: AsyncClient):
        """What: Explicit JSON null for required string field.
        Why: Documents Pydantic/FastAPI rejection vs. empty string.
        Expected: 422 Unprocessable Entity."""
        r = await http_client.post("/ingest/text", json={"text": None})
        assert r.status_code == 422


@pytest.mark.eval
class TestInputBoundariesQueryInjectionStrings:
    """Adversarial *strings* in query fields must not break the placeholder API."""

    @pytest.mark.asyncio
    async def test_sql_and_cypher_like_question_still_200(self, http_client: AsyncClient):
        """What: Question containing SQL/Cypher/HTML metacharacters.
        Why: Ensures no unsafe interpolation or crashes at the API boundary today.
        Expected: 200 JSON placeholder answer (pipeline not executed)."""
        payload = {
            "question": "'; DROP TABLE users; -- "
            "MATCH (n) DETACH DELETE n "
            "<script>alert(1)</script>",
            "regulation_id": None,
            "use_graph_rag": True,
            "top_k": 10,
        }
        r = await http_client.post("/query", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert "answer" in body


# ---------------------------------------------------------------------------
# regulation_id URL / path edge cases
# ---------------------------------------------------------------------------


@pytest.mark.eval
class TestRegulationIdEdgeCases:
    """Path parameter handling for `/impact/{regulation_id}`."""

    @pytest.mark.asyncio
    async def test_nonexistent_id_still_returns_placeholder_200(self, http_client: AsyncClient):
        """What: Arbitrary ID with no graph backing.
        Why: Current handler is a stub; callers should get a stable response.
        Expected: 200 with regulation_id echoed."""
        rid = "does-not-exist-999"
        r = await http_client.get(f"/impact/{rid}")
        assert r.status_code == 200
        assert r.json()["regulation_id"] == rid

    @pytest.mark.asyncio
    async def test_empty_regulation_id_in_compliance_query_accepted(self, http_client: AsyncClient):
        """What: ``regulation_id`` sent as empty string on POST `/query`.
        Why: Clients often send "" instead of omitting the field.
        Expected: 200; empty string normalized to ``None`` in trace."""
        r = await http_client.post(
            "/query",
            json={"question": "Scoped?", "regulation_id": "", "top_k": 10},
        )
        assert r.status_code == 200
        assert r.json()["trace"]["regulation_id"] is None

    @pytest.mark.asyncio
    async def test_special_characters_url_encoded(self, http_client: AsyncClient):
        """What: ID containing characters that must be percent-encoded in URLs.
        Why: Proxies and logs often mangle unescaped paths.
        Expected: 200; decoded id matches intended string."""
        from urllib.parse import quote

        raw = "reg<script>&\"'"
        r = await http_client.get(f"/impact/{quote(raw, safe='')}")
        assert r.status_code == 200
        assert r.json()["regulation_id"] == raw


# ---------------------------------------------------------------------------
# State machine & orchestration engine
# ---------------------------------------------------------------------------


@pytest.mark.eval
class TestStateMachineEdgeCases:
    """ARIAState predicates, routing, error-at-entry, re-entry, and bad nodes."""

    def test_raw_document_and_regulation_id_both_set_prefers_ingestion(self):
        """What: `raw_document` and `regulation_id` populated together.
        Why: Conflicting intents should have deterministic routing.
        Expected: `is_ingestion_request` wins; supervisor routes to `ingestion`."""
        state = ARIAState(raw_document="body", regulation_id="REG-1")
        assert state.is_ingestion_request
        assert not state.is_impact_query
        assert route_after_supervisor(state) == "ingestion"

    @pytest.mark.asyncio
    async def test_error_set_before_supervisor_routes_to_end(self):
        """What: `error` populated before the first supervisor step.
        Why: Fail-fast avoids running downstream nodes on poisoned state.
        Expected: Edge routes to `end` immediately after supervisor."""
        state = ARIAState(error="precondition failed")
        tools = _StubTools()
        await supervisor_node(state, tools)
        assert route_after_supervisor(state) == "end"

    @pytest.mark.asyncio
    async def test_re_entry_appends_to_existing_history(self):
        """What: Execute graph with non-empty `history`.
        Why: Retries or nested calls should not assume a blank audit trail.
        Expected: New steps append; path grows."""
        from aria.orchestration.scratch.graph import build_default_graph

        graph = build_default_graph()
        tools = _StubTools()
        state = ARIAState(
            raw_document="short doc",
            history=["prior_supervisor"],
        )
        result = await graph.execute(state, tools)
        assert "prior_supervisor" in result.final_state.history
        assert result.final_state.history[0] == "prior_supervisor"
        assert len(result.final_state.history) > 1

    @pytest.mark.asyncio
    async def test_ingestion_node_empty_raw_document_sets_error(self):
        """What: ``raw_document`` is empty string (falsy).
        Why: Distinguishes API validation from orchestration node guards.
        Expected: Error message set; no extractor call."""
        state = ARIAState(raw_document="")
        tools = _StubTools()
        out = await ingestion_node(state, tools)
        assert out.error is not None
        assert "no raw_document" in out.error.lower()

    @pytest.mark.asyncio
    async def test_node_returning_none_sets_error_and_terminates(self):
        """What: Registered node returns ``None`` instead of ``ARIAState``.
        Why: Bad plugins must not crash the engine with ``AttributeError``.
        Expected: Prior state preserved, ``error`` set, run ends without raising."""

        async def broken_node(state: ARIAState, tools: ToolPorts) -> ARIAState | None:
            return None  # type: ignore[return-value]

        g = OrchestrationGraph(entry_point="bad")
        g.add_node("bad", broken_node)
        g.add_edge("bad", route_after_supervisor)

        initial = ARIAState(raw_document="x")
        result = await g.execute(initial, _StubTools())
        assert not result.success
        assert result.final_state.error is not None
        assert "invalid state" in result.final_state.error.lower()
        assert result.final_state.raw_document == "x"


# ---------------------------------------------------------------------------
# Contract boundaries — domain models
# ---------------------------------------------------------------------------


@pytest.mark.eval
class TestContractExtractedEntities:
    """Volume and shape constraints on extraction output."""

    def test_zero_regulations_valid(self):
        """What: `ExtractedEntities` with empty regulations list.
        Why: Empty extractions are legitimate for irrelevant documents.
        Expected: Model validates."""
        ee = ExtractedEntities(source_document_hash="h", regulations=[])
        assert ee.regulations == []

    def test_large_regulation_list_validates(self):
        """What: 1000 minimal `Regulation` rows.
        Why: Stresses validation and memory for bulk synthetic data.
        Expected: Single successful validation."""
        regs = [
            Regulation(
                id=f"reg-{i}",
                title="T",
                jurisdiction="eu",
                domain="privacy",
            )
            for i in range(1000)
        ]
        ee = ExtractedEntities(source_document_hash="bulk", regulations=regs)
        assert len(ee.regulations) == 1000


@pytest.mark.eval
class TestContractRequirement:
    """Field-level validation on requirements."""

    def test_empty_text_allowed(self):
        """What: `Requirement.text` is empty string.
        Why: Bad LLM output may still be structurally valid.
        Expected: Pydantic accepts (callers may enforce stricter rules)."""
        req = Requirement(
            id="r1",
            text="",
            obligation_type=ObligationType.REQUIREMENT,
        )
        assert req.text == ""

    def test_obligation_type_not_in_enum_rejected(self):
        """What: Invalid obligation_type string.
        Why: Prevents silent coercion to wrong obligation semantics.
        Expected: ValidationError."""
        with pytest.raises(ValidationError):
            Requirement(
                id="r1",
                text="x",
                obligation_type="not_a_real_type",  # type: ignore[arg-type]
            )


@pytest.mark.eval
class TestContractImpactReport:
    """Risk computation when counts are degenerate."""

    def test_total_requirements_zero_no_division_error(self):
        """What: `total_requirements=0`, no gaps.
        Why: Guard against ZeroDivisionError in `risk_level`.
        Expected: LOW risk (gap_count 0 short-circuit)."""
        report = ImpactReport(
            regulation_id="r",
            regulation_title="t",
            total_requirements=0,
            coverage_summary={},
        )
        assert report.risk_level == RiskLevel.LOW

    def test_total_requirements_zero_with_gaps_normalizes_and_risk(self):
        """What: Gaps recorded while `total_requirements` stays 0 (inconsistent input).
        Why: Validator aligns totals to gap count; risk uses a bounded denominator.
        Expected: ``total_requirements`` becomes gap count; all gaps → CRITICAL risk."""
        report = ImpactReport(
            regulation_id="r",
            regulation_title="t",
            total_requirements=0,
            coverage_summary={CoverageStatus.GAP: 3},
        )
        assert report.gap_count == 3
        assert report.total_requirements == 3
        assert report.risk_level == RiskLevel.CRITICAL


@pytest.mark.eval
class TestContractGraphWritePayload:
    """Payload shape vs. Neo4j write semantics."""

    def test_duplicate_node_ids_same_label_allowed_in_payload(self):
        """What: Two `GraphNode` rows with same label + same `id`.
        Why: Duplicates may come from bad extractors; MERGE is idempotent.
        Expected: Model validates; fixture lists two TEAM nodes with same id."""
        p = ADV_DUPLICATE_NODE_IDS_SAME_LABEL
        assert len(p.nodes) == 2
        assert p.nodes[0].properties["id"] == p.nodes[1].properties["id"]
        GraphWritePayload.model_validate(p.model_dump())


# ---------------------------------------------------------------------------
# LLM client — structured JSON parsing
# ---------------------------------------------------------------------------


@pytest.mark.eval
class TestLLMClientCompleteStructured:
    """Behavior of `complete_structured` against hostile or sloppy LLM text."""

    @pytest.mark.asyncio
    async def test_plain_json_object(self):
        """What: Response is raw JSON without fences.
        Why: Some models ignore markdown instructions.
        Expected: Parsed model."""
        client = LLMClient()
        with patch.object(client, "complete", new_callable=AsyncMock) as m:
            m.return_value = '{"answer": "ok", "score": 2}'
            out = await client.complete_structured(
                [{"role": "user", "content": "hi"}],
                _TinyStructured,
            )
        assert out.answer == "ok"
        assert out.score == 2

    @pytest.mark.asyncio
    async def test_json_inside_single_markdown_fence(self):
        """What: ```json ... ``` wrapper (happy path for prompt contract).
        Why: Matches documented fallback in `LLMClient.complete_structured`.
        Expected: Inner JSON parsed."""
        client = LLMClient()
        raw = '```json\n{"answer": "fenced", "score": 1}\n```'
        with patch.object(client, "complete", new_callable=AsyncMock) as m:
            m.return_value = raw
            out = await client.complete_structured(
                [{"role": "user", "content": "hi"}],
                _TinyStructured,
            )
        assert out.answer == "fenced"

    @pytest.mark.asyncio
    async def test_non_json_raises(self):
        """What: Free-text response.
        Why: Callers must handle parse failures from flaky providers.
        Expected: ValidationError from `model_validate_json`."""
        client = LLMClient()
        with patch.object(client, "complete", new_callable=AsyncMock) as m:
            m.return_value = "This is not JSON at all."
            with pytest.raises(ValidationError):
                await client.complete_structured(
                    [{"role": "user", "content": "hi"}],
                    _TinyStructured,
                )

    @pytest.mark.asyncio
    async def test_partial_json_raises(self):
        """What: Truncated JSON object.
        Why: Streaming or token limits often produce invalid JSON.
        Expected: ValidationError."""
        client = LLMClient()
        with patch.object(client, "complete", new_callable=AsyncMock) as m:
            m.return_value = '{"answer": "cut'
            with pytest.raises(ValidationError):
                await client.complete_structured(
                    [{"role": "user", "content": "hi"}],
                    _TinyStructured,
                )

    @pytest.mark.asyncio
    async def test_json_with_extra_fields_ignored_by_default(self):
        """What: Valid JSON with additional keys.
        Why: Pydantic v2 default ignores extras unless configured otherwise.
        Expected: Model validates; unknown keys dropped."""
        client = LLMClient()
        with patch.object(client, "complete", new_callable=AsyncMock) as m:
            m.return_value = '{"answer": "x", "extra": 99, "nested": {"a": 1}}'
            out = await client.complete_structured(
                [{"role": "user", "content": "hi"}],
                _TinyStructured,
            )
        assert out.answer == "x"

    @pytest.mark.asyncio
    async def test_double_opening_fence_parsed_after_remediation(self):
        """What: Two consecutive opening fences before JSON (model confusion).
        Why: Nested ``` lines are common; parser should skip stray openings.
        Expected: Valid structured output."""
        client = LLMClient()
        raw = '```json\n```json\n{"answer": "nested", "score": 0}\n```'
        with patch.object(client, "complete", new_callable=AsyncMock) as m:
            m.return_value = raw
            out = await client.complete_structured(
                [{"role": "user", "content": "hi"}],
                _TinyStructured,
            )
        assert out.answer == "nested"
        assert out.score == 0

    @pytest.mark.asyncio
    async def test_leading_prose_then_json_object(self):
        """What: Explanatory text before a raw JSON object (no fences).
        Why: Chatty models often prefix the payload.
        Expected: First balanced object extracted and validated."""
        client = LLMClient()
        raw = 'Here you go: {"answer": "prose", "score": 7} — end.'
        with patch.object(client, "complete", new_callable=AsyncMock) as m:
            m.return_value = raw
            out = await client.complete_structured(
                [{"role": "user", "content": "hi"}],
                _TinyStructured,
            )
        assert out.answer == "prose"
        assert out.score == 7

    @pytest.mark.asyncio
    async def test_empty_and_whitespace_only_response_raises(self):
        """What: Empty or whitespace LLM output.
        Why: No JSON to parse.
        Expected: ValidationError."""
        client = LLMClient()
        for bad in ("", "   \n\t  "):
            with patch.object(client, "complete", new_callable=AsyncMock) as m:
                m.return_value = bad
                with pytest.raises(ValidationError):
                    await client.complete_structured(
                        [{"role": "user", "content": "hi"}],
                        _TinyStructured,
                    )


# ---------------------------------------------------------------------------
# HTTP API — transport and validation
# ---------------------------------------------------------------------------


@pytest.mark.eval
class TestAPIEdgeCases:
    """FastAPI/Starlette behavior for methods, headers, concurrency, and schema."""

    @pytest.mark.asyncio
    async def test_wrong_method_returns_405(self, http_client: AsyncClient):
        """What: GET on a POST-only ingest route.
        Why: Clients misconfigured method should not hit handler.
        Expected: 405 Method Not Allowed."""
        r = await http_client.get("/ingest/text")
        assert r.status_code == 405

    @pytest.mark.asyncio
    async def test_missing_content_type_json_body_still_decoded(self, http_client: AsyncClient):
        """What: Raw JSON bytes without ``Content-Type: application/json``.
        Why: Browsers and proxies sometimes omit or strip headers.
        Expected: With httpx + Starlette/FastAPI, JSON may still decode and return 200;
        a stricter proxy could return 415/422 instead — this run documents local behavior."""
        r = await http_client.post(
            "/ingest/text",
            content=json.dumps({"text": "hello", "source": "t"}).encode(),
            headers={},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    @pytest.mark.asyncio
    async def test_oversized_text_body_still_accepted(self, http_client: AsyncClient):
        """What: Large (multi-MB) JSON string for `text`.
        Why: Ensures no trivial size cap at app layer for legitimate corpora.
        Expected: 200 and non-zero chunks (chunker runs)."""
        big = "Sentence one. " * 150_000
        r = await http_client.post("/ingest/text", json={"text": big})
        assert r.status_code == 200
        assert r.json()["chunks_produced"] >= 1

    @pytest.mark.asyncio
    async def test_concurrent_posts_to_query_endpoint(self, http_client: AsyncClient):
        """What: Many parallel POSTs to `/query` with distinct bodies.
        Why: Same route + async handlers should remain stable under burst.
        Expected: All 200."""

        async def hit(i: int) -> int:
            resp = await http_client.post(
                "/query",
                json={"question": f"Concurrent question {i}?", "top_k": 10},
            )
            return resp.status_code

        codes = await asyncio.gather(*(hit(i) for i in range(24)))
        assert all(c == 200 for c in codes)

    @pytest.mark.asyncio
    async def test_query_extra_fields_return_422(self, http_client: AsyncClient):
        """What: POST `/query` with unknown top-level keys.
        Why: Public API models use ``extra='forbid'`` for predictable contracts.
        Expected: 422 validation error."""
        r = await http_client.post(
            "/query",
            json={
                "question": "Q?",
                "unexpected_field": {"nested": True},
                "top_k": 5,
            },
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_ingest_text_extra_fields_return_422(self, http_client: AsyncClient):
        """What: POST ``/ingest/text`` with keys not on ``IngestTextRequest``.
        Why: Same strict contract as query endpoint.
        Expected: 422."""
        r = await http_client.post(
            "/ingest/text",
            json={"text": "hello", "source": "t", "evil": True},
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_ingest_rejects_content_length_over_limit(
        self, http_client: AsyncClient, monkeypatch
    ):
        """What: ``Content-Length`` above ``MAX_INGEST_BODY_BYTES``.
        Why: Protects workers from huge JSON bodies (checked before body read).
        Expected: 413."""
        import api.limits

        monkeypatch.setattr(api.limits, "MAX_INGEST_BODY_BYTES", 300)
        r = await http_client.post(
            "/ingest/text",
            json={"text": "x" * 500, "source": "t"},
        )
        assert r.status_code == 413
        assert "exceeds" in r.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_top_k_out_of_range_returns_422(self, http_client: AsyncClient):
        """What: `top_k` below minimum or above maximum.
        Why: Bounds prevent accidental huge retrieval fan-out.
        Expected: 422 validation error from Pydantic."""
        r_low = await http_client.post(
            "/query",
            json={"question": "x", "top_k": 0},
        )
        r_high = await http_client.post(
            "/query",
            json={"question": "x", "top_k": 99},
        )
        assert r_low.status_code == 422
        assert r_high.status_code == 422
