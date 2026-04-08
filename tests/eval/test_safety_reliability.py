"""Safety and reliability evaluation: failure injection without live services.

Each test documents:
- Failure mode injected (what breaks)
- Expected system response (how the code is designed to react)
- Actual impact (what state or data can still be wrong)

Run: pytest tests/eval/test_safety_reliability.py -v --tb=short -m eval
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from aria.contracts.graph_entities import GraphNode, GraphWritePayload, GraphWriteStatus, NodeLabel
from aria.contracts.regulation import ExtractedEntities
from aria.graph.builder import write_payload
from aria.graph.client import Neo4jClient
from aria.ingestion.chunker import DocumentChunk, chunk_text
from aria.ingestion.parsers.pdf_parser import parse_pdf
from aria.ingestion.pipeline import IngestionStatus, ingest_document, reset_ingestion_state
from aria.llm.client import LLMClient
from aria.orchestration.scratch.nodes import entity_extractor_node
from aria.orchestration.scratch.state import ARIAState
from aria.retrieval.vector_store import VectorStore

pytestmark = pytest.mark.eval

SAMPLE_HTML = """<!DOCTYPE html><html><head><title>T</title></head><body>
<h1>Article 1</h1><p>First sentence for chunking. Second sentence here.</p>
</body></html>"""


@pytest.fixture(autouse=True)
def _clean_ingestion_hashes():
    reset_ingestion_state()
    yield
    reset_ingestion_state()


# ---------------------------------------------------------------------------
# Failure cascades
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_neo4j_unreachable_connect_fails_fast(tmp_path: Path) -> None:
    """Failure: Neo4j not accepting connections during verify_connectivity.

    Expected: connect() raises — startup/API paths fail loudly (no silent continue).
    Impact: No half-open client; caller must handle or abort (not a degraded read-only mode).
    """
    with patch("aria.graph.client.AsyncGraphDatabase.driver") as drv:
        mock_driver = MagicMock()
        mock_driver.verify_connectivity = AsyncMock(
            side_effect=ConnectionError("Neo4j unreachable")
        )
        drv.return_value = mock_driver

        client = Neo4jClient("bolt://localhost:7687", "neo4j", "x")
        with pytest.raises(ConnectionError, match="Neo4j unreachable"):
            await client.connect()


@pytest.mark.asyncio
async def test_neo4j_health_check_degrades_to_false() -> None:
    """Failure: Bolt read fails at runtime (network partition, auth, etc.).

    Expected: health_check() catches exceptions and returns False (no crash).
    Impact: Callers see unhealthy status; they must branch on False — data may be stale.
    """
    client = Neo4jClient("bolt://localhost:7687", "neo4j", "x")
    mock_session = AsyncMock()
    mock_session.run = AsyncMock(side_effect=RuntimeError("session dead"))

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=None)

    mock_driver = MagicMock()
    mock_driver.session = MagicMock(return_value=cm)
    client._driver = mock_driver

    ok = await client.health_check()
    assert ok is False


@pytest.mark.asyncio
async def test_llm_garbage_json_does_not_yield_entities_for_graph(tmp_path: Path) -> None:
    """Failure: LLM returns non-JSON / schema-invalid payload.

    Expected: complete_structured raises ValidationError before any graph write port runs.
    Impact: No validated ExtractedEntities — orchestration nodes set error; graph_writer
    in pipeline is never reached when extraction raises.
    """
    client = LLMClient(max_retries=1)

    with patch.object(client, "complete", new_callable=AsyncMock, return_value="not valid json {{{"):
        with pytest.raises(ValidationError):
            await client.complete_structured(
                [{"role": "user", "content": "x"}],
                ExtractedEntities,
            )

    html_file = tmp_path / "r.html"
    html_file.write_text(SAMPLE_HTML, encoding="utf-8")

    async def bad_extract(_text: str, _h: str) -> ExtractedEntities:
        raise ValidationError.from_exception_data("x", [])

    graph_calls: list[int] = []

    async def graph_writer(_e: ExtractedEntities) -> GraphWriteStatus:
        graph_calls.append(1)
        return GraphWriteStatus()

    result = await ingest_document(
        html_file,
        entity_extractor=bad_extract,
        graph_writer=graph_writer,
    )
    assert result.status == IngestionStatus.EXTRACTION_ERROR
    assert graph_calls == []


@pytest.mark.asyncio
async def test_chroma_vector_failure_partial_ingestion_not_committed_to_hash_set(
    tmp_path: Path,
) -> None:
    """Failure: Vector indexer (Chroma) raises after parse/chunk/extract/graph succeed.

    Expected: Status PARTIAL_FAILURE; duplicate hash set is NOT updated (retry allowed).
    Impact: Graph side effects may already exist from graph_writer; vectors missing until
    retry. MERGE-based graph writes stay idempotent on retry.
    """
    html_file = tmp_path / "r.html"
    html_file.write_text(SAMPLE_HTML, encoding="utf-8")

    async def ok_extract(text: str, h: str) -> ExtractedEntities:
        return ExtractedEntities(source_document_hash=h)

    async def ok_graph(_e: ExtractedEntities) -> GraphWriteStatus:
        return GraphWriteStatus()

    async def chroma_down(_chunks) -> bool:
        raise ConnectionError("ChromaDB down")

    r = await ingest_document(
        html_file,
        entity_extractor=ok_extract,
        graph_writer=ok_graph,
        vector_indexer=chroma_down,
    )
    assert r.status == IngestionStatus.PARTIAL_FAILURE
    assert "Vector indexing failed" in r.errors[0]

    r2 = await ingest_document(html_file, entity_extractor=ok_extract, graph_writer=ok_graph)
    assert r2.status != IngestionStatus.SKIPPED_DUPLICATE


# ---------------------------------------------------------------------------
# Data integrity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotency_same_document_hash_skips_second_ingest(tmp_path: Path) -> None:
    """Failure: N/A (happy path for idempotency contract).

    Expected: Second ingest with same content hash → SKIPPED_DUPLICATE (no duplicate nodes
    from this pipeline path; graph_writer not invoked again).
    Impact: Relies on in-process _ingested_hashes — process restart loses memory (documented).
    """
    html_file = tmp_path / "r.html"
    html_file.write_text(SAMPLE_HTML, encoding="utf-8")
    calls: list[int] = []

    async def counting_graph(_e: ExtractedEntities) -> GraphWriteStatus:
        calls.append(1)
        return GraphWriteStatus()

    async def extract_entities(_t: str, h: str) -> ExtractedEntities:
        return ExtractedEntities(source_document_hash=h)

    r1 = await ingest_document(
        html_file,
        entity_extractor=extract_entities,
        graph_writer=counting_graph,
    )
    r2 = await ingest_document(
        html_file,
        entity_extractor=extract_entities,
        graph_writer=counting_graph,
    )
    assert r1.status == IngestionStatus.SUCCESS
    assert r2.status == IngestionStatus.SKIPPED_DUPLICATE
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_content_hash_collision_second_document_treated_as_duplicate(
    tmp_path: Path,
) -> None:
    """Failure: Two distinct byte streams with identical SHA-256 (theoretical).

    Expected: Pipeline keys only on content_hash — second file is skipped as duplicate.
    Impact: Second document never ingested; silent data loss unless operators use force=True
    or an out-of-band dedup key. SHA-256 collision risk is negligible but behavior is defined.
    """
    from aria.ingestion import pipeline as pipeline_mod

    path_a = tmp_path / "a.html"
    path_b = tmp_path / "b.html"
    path_a.write_text("<html><body><p>one</p></body></html>", encoding="utf-8")
    path_b.write_text("<html><body><p>two</p></body></html>", encoding="utf-8")

    h = "c0ffee" + "ab" * 29  # 64-char hex-shaped idempotency key

    with (
        patch.object(pipeline_mod, "_detect_format", return_value=pipeline_mod.DocumentFormat.HTML),
        patch.object(
            pipeline_mod,
            "_parse_document",
            side_effect=[("text one", h), ("text two different", h)],
        ),
    ):
        r1 = await ingest_document(path_a)
        r2 = await ingest_document(path_b)

    assert r1.status == IngestionStatus.SUCCESS
    assert r2.status == IngestionStatus.SKIPPED_DUPLICATE


@pytest.mark.asyncio
async def test_graph_batch_write_transaction_rolls_back_on_mid_batch_failure() -> None:
    """Failure: Mid-batch node write raises (constraint, syntax, transient).

    Expected: Single Neo4j transaction — failure aborts the whole batch; no partial commit.
    Impact: Graph stays consistent for this payload; caller sees one aggregated error (counters
    reflect no successful commit when the driver rolls back).
    """
    calls: list[int] = []

    async def flaky_run(cypher: str, params: dict | None = None):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("second node failed")
        result = MagicMock()
        result.consume = AsyncMock(
            return_value=MagicMock(counters=MagicMock(nodes_created=1, relationships_created=0))
        )
        return result

    mock_tx = AsyncMock()
    mock_tx.run = flaky_run
    mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
    mock_tx.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock()
    mock_session.begin_transaction = AsyncMock(return_value=mock_tx)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=None)

    client = MagicMock(spec=Neo4jClient)
    client.session = MagicMock(return_value=cm)

    payload = GraphWritePayload(
        nodes=[
            GraphNode(label=NodeLabel.JURISDICTION, properties={"id": "j1", "name": "EU", "region": "EU"}),
            GraphNode(label=NodeLabel.JURISDICTION, properties={"id": "j2", "name": "US", "region": "NA"}),
        ]
    )
    status = await write_payload(client, payload)
    assert not status.success
    assert len(status.errors) >= 1
    assert len(calls) == 2
    assert "transaction failed" in status.errors[0].lower()


# ---------------------------------------------------------------------------
# Retry and timeout (LLMClient)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_client_retries_three_times_then_raises() -> None:
    """Failure: litellm.acompletion raises on every attempt.

    Expected: Exactly max_retries attempts, then the last exception propagates.
    Impact: No partial text returned; callers see failure after bounded retries.
    """
    client = LLMClient(max_retries=3, timeout=30.0)
    attempts: list[int] = []

    async def boom(**kwargs):
        attempts.append(1)
        raise ConnectionError("LLM unavailable")

    with patch("aria.llm.client.litellm.acompletion", side_effect=boom):
        with pytest.raises(ConnectionError, match="LLM unavailable"):
            await client.complete([{"role": "user", "content": "hi"}])

    assert len(attempts) == 3


@pytest.mark.asyncio
async def test_llm_client_timeout_kwarg_passed_to_litellm() -> None:
    """Failure: Underlying client times out (simulated immediate TimeoutError).

    Expected: Each attempt passes timeout= to litellm.acompletion; after retries, raises.
    Impact: Hung providers bounded by 120s default per attempt (configurable on LLMClient).
    """
    captured: list[float] = []

    async def record_timeout(**kwargs):
        captured.append(float(kwargs.get("timeout", 0.0)))
        raise asyncio.TimeoutError()

    client = LLMClient(max_retries=2, timeout=120.0)
    with patch("aria.llm.client.litellm.acompletion", side_effect=record_timeout):
        with pytest.raises(asyncio.TimeoutError):
            await client.complete([{"role": "user", "content": "x"}])

    assert len(captured) == 2
    assert all(t == 120.0 for t in captured)


@pytest.mark.asyncio
async def test_llm_retries_idempotent_no_extra_success_payload() -> None:
    """Failure: Transient errors on first calls; success on last.

    Expected: Retries only re-invoke the LLM; successful completion returns one final string.
    Impact: No client-side persistence of failed partial responses — side effects are
    retry calls only (idempotent for read-only completion use case).
    """
    client = LLMClient(max_retries=3)
    n = {"i": 0}

    async def flaky(**kwargs):
        n["i"] += 1
        if n["i"] < 3:
            raise ConnectionError("transient")
        resp = MagicMock()
        resp.choices = [MagicMock(message=MagicMock(content="final"))]
        return resp

    with patch("aria.llm.client.litellm.acompletion", side_effect=flaky):
        out = await client.complete([{"role": "user", "content": "x"}])

    assert out == "final"
    assert n["i"] == 3


# ---------------------------------------------------------------------------
# State corruption / isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_entity_extractor_node_does_not_mutate_prior_run_state_template() -> None:
    """Failure: Buggy node might reuse same ARIAState instance (simulated).

    Expected: Fresh state per run — error on run A does not appear on unrelated fresh state B.
    Impact: Isolation is by convention (new BaseModel instances); shared mutable singletons
    (e.g. module _ingested_hashes) are global unless reset.

    Uses ``entity_extractor_node`` (extraction); ``ingestion_node`` only validates document input.
    """
    tools = MagicMock()
    tools.extract_entities = AsyncMock(side_effect=ValidationError.from_exception_data("e", []))

    s1 = ARIAState(raw_document="doc", document_hash="h1")
    out1 = await entity_extractor_node(s1, tools)
    assert out1.error is not None

    tools.extract_entities = AsyncMock(
        return_value=ExtractedEntities(source_document_hash="h2").model_dump()
    )
    s2 = ARIAState(raw_document="doc2", document_hash="h2")
    out2 = await entity_extractor_node(s2, tools)
    assert out2.error is None
    assert out2.extracted_entities is not None


def test_module_level_ingestion_hash_set_is_shared_across_calls() -> None:
    """Failure: Malicious/buggy code could rely on stale global dedup state.

    Expected: Documented behavior — _ingested_hashes is process-wide; reset_ingestion_state()
    clears it for tests/long-running workers that need a fresh view.
    Impact: Two logical tenants in one process share dedup unless partitioned externally.
    """
    from aria.ingestion import pipeline as p

    p._ingested_hashes.add("fixed")
    assert "fixed" in p._ingested_hashes
    reset_ingestion_state()
    assert "fixed" not in p._ingested_hashes


# ---------------------------------------------------------------------------
# Resource management
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_neo4j_session_context_exits_on_execute_read_error() -> None:
    """Failure: Query raises inside session.

    Expected: Async context manager __aexit__ still runs (driver releases session).
    Impact: Prevents connection leaks on error paths (assuming driver honors context protocol).
    """
    mock_session = AsyncMock()
    mock_session.run = AsyncMock(side_effect=RuntimeError("read failed"))

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=None)

    mock_driver = MagicMock()
    mock_driver.session = MagicMock(return_value=cm)

    client = Neo4jClient("bolt://x", "u", "p")
    client._driver = mock_driver

    with pytest.raises(RuntimeError, match="read failed"):
        await client.execute_read("RETURN 1")

    cm.__aexit__.assert_awaited()


def test_pdf_parser_closes_plumber_context_on_page_iteration_error(tmp_path: Path) -> None:
    """Failure: Exception while iterating pdf.pages.

    Expected: pdfplumber.open context manager __exit__ runs (file released).
    Impact: Avoids leaking FDs on corrupt/malicious PDFs mid-parse.
    """
    p = tmp_path / "f.pdf"
    p.write_bytes(b"%PDF-1.4")

    class FakePDF:
        def __init__(self) -> None:
            self.exited = False

        def __enter__(self) -> FakePDF:
            return self

        def __exit__(self, *args: object) -> bool:
            self.exited = True
            return False

        @property
        def pages(self) -> list[object]:
            raise RuntimeError("boom")

    fake = FakePDF()
    with patch("aria.ingestion.parsers.pdf_parser.pdfplumber.open", return_value=fake):
        with pytest.raises(RuntimeError, match="boom"):
            parse_pdf(p)

    assert fake.exited is True


def test_chunker_large_document_completes_bounded_chunks() -> None:
    """Failure: Very large in-memory string (memory pressure).

    Expected: chunk_text builds a list proportional to text/chunk_size (no unbounded recursion).
    Impact: Entire document still held in memory once; streaming chunking is not implemented.
    """
    sentence = "This is one regulatory sentence for stress. "
    text = sentence * 8000
    chunks = chunk_text(text, source_hash="stress", chunk_size=200, chunk_overlap=40)
    assert len(chunks) >= 10
    assert all(len(c.text) > 0 for c in chunks)


def test_vector_store_not_connected_raises_clear_error() -> None:
    """Failure: Vector operations called without connect().

    Expected: RuntimeError from collection accessor (fail fast).
    Impact: Callers must establish connection lifecycle; index_chunks([]) is a no-op and
    does not touch the collection — use a path that requires a live client.
    """
    vs = VectorStore(host="127.0.0.1", port=59999)
    with pytest.raises(RuntimeError, match="not connected"):
        vs.index_chunks(
            [
                DocumentChunk(
                    chunk_id="c1",
                    text="x",
                    source_document_hash="h",
                    metadata={},
                )
            ]
        )
