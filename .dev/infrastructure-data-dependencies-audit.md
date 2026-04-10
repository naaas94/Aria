# Infrastructure & data dependencies — QA audit

**Topic:** Chroma 1.x usage, Neo4j + ingestion pipeline, Docker Compose & env alignment.  
**Date:** 2026-04-09  
**Note:** Tests were not executed as part of this write-up; CI status is not claimed.

---

## Executive summary

- **Chroma 1.x is wired consistently** in code, Docker, CI, and `pyproject.toml`: `HttpClient`, collection metadata, and `/api/v2/heartbeat` match the server image `chromadb/chroma:1.5.6` (not 0.5.x-style assumptions visible in-repo).
- **Neo4j ingestion/graph path is sound for idempotency** where used: MERGE-based writes in one transaction, optional `IngestionRecord` dedup via parameterized Cypher.
- **Highest practical risk found: env default mismatch for `NEO4J_PASSWORD`** between `/ready` and `connect_app_dependencies()`, which can make readiness **green while the app never obtains a Neo4j driver** (or the reverse), if the password is unset.
- **HTTP `/ingest/*` is not the full ingestion pipeline** (no graph, vectors, or `neo4j_dedup`); durable dedup and multi-stage behavior are library/script concerns unless wired elsewhere.
- **Operational gaps**: global in-process dedup set does not span workers; `list_complete_content_hashes` has no cap (large graphs); **SQLite telemetry** uses WAL + lock but remains a **single-writer** store under concurrent load.
- **Docs**: `.env.example` is more accurate than README on unauthenticated routes (`/metrics`, `/telemetry`, `/ready`); README overstates “except `/health`” for API key gating.

---

## Scope map

| Area | Primary locations |
|------|-------------------|
| Chroma client & collection | `aria/retrieval/vector_store.py` |
| Chroma readiness / heartbeat | `api/readiness.py` (`check_chroma`) |
| App wiring | `api/connections.py`, `api/main.py` (lifespan) |
| Neo4j driver | `aria/graph/client.py` |
| Graph writes | `aria/graph/builder.py` (`write_payload`, MERGE helpers) |
| Ingestion dedup / progress | `aria/ingestion/pipeline.py`, `aria/graph/ingestion_record.py` |
| HTTP ingest (limited) | `api/routers/ingest.py` |
| Docker / images | `docker-compose.yml`, `.github/workflows/nightly.yml` |
| Deps | `pyproject.toml`, `uv.lock` |
| Telemetry DB | `aria/observability/telemetry_store.py` |
| Config / docs | `.env.example`, `README.md` (Hardening, Quickstart) |
| Tests | `tests/integration/test_ingestion_pipeline.py`, `tests/eval/test_safety_reliability.py`, `tests/eval/test_security_audit.py` |

---

## Findings

| Sev | Finding | Evidence | Impact | Recommendation |
|-----|---------|----------|--------|----------------|
| **P1** | **`NEO4J_PASSWORD` defaults differ** between readiness and app connection: readiness defaults to `aria_dev_password`; lifespan connection defaults to **empty string**. | `api/readiness.py` (lines 17–19) vs `api/connections.py` (lines 55–56) | If `NEO4J_URI` is set but `NEO4J_PASSWORD` is **unset**, `/ready` may report `neo4j: true` while `AppConnections.neo4j` stays `None` after failed auth — **misleading readiness** and confusing ops. | Use the **same default** for both paths, or **require** explicit password when `NEO4J_URI` is set (fail fast with clear log). |
| **P2** | **`/ready` does not consult `app.state.connections`**; it opens **new** Neo4j + HTTP clients per request. | `api/main.py` (lines 155–161); `api/readiness.py` (`check_neo4j`, `check_chroma`) | Extra Bolt connects per probe; under aggressive K8s probes, **load on Neo4j** and churn; can also **diverge** from actual app wiring if env were ever inconsistent (same process, rare). | Optionally reuse pooled driver from `app.state` or cache probe result with short TTL; align probe credentials with `connect_app_dependencies`. |
| **P2** | **In-process `_ingested_hashes` is per-process**; `neo4j_dedup` hydrates once per process. | `aria/ingestion/pipeline.py` (`_ingested_hashes`, `_hydrate_dedup_from_neo4j`) | **Multiple uvicorn workers** or separate ingest jobs: duplicate work unless **`neo4j_dedup`** is always used and Neo4j is authoritative. | Document multi-worker requirement; ensure any production ingest path passes **`neo4j_dedup`**. |
| **P2** | **`list_complete_content_hashes` loads all complete hashes** with no pagination. | `aria/graph/ingestion_record.py` (`list_complete_content_hashes`) | After many ingested docs, **startup/hydration cost** and memory grow; risk of slow first-ingest after restart. | Paginate or cap + incremental sync (needs runtime sizing to validate). |
| **P2** | **HTTP ingest only chunks text** — no `ingest_document`, no graph/vector/dedup. | `api/routers/ingest.py` | Operators may assume **`/ingest/text`** drives the full pipeline; **no Neo4j/Chroma** involvement. | Clarify in README/API description; or wire optional full pipeline behind a flag (larger scope). |
| **P3** | **README vs code: API key** claims routes are gated “except `/health`”. | `README.md` (~line 116) vs `api/main.py` (telemetry router without `_route_auth`; `/ready` unauthenticated) | **Security/ops misunderstanding** (metrics/telemetry exposure). | Fix README to list **`/health`, `/ready`, `/metrics`, `/telemetry`** (and any others) explicitly; `.env.example` lines 46–48 are closer to truth. |
| **P3** | **Two upload/body limits**: middleware uses `ARIA_MAX_INGEST_BODY_BYTES` (default 12 MiB); multipart uses `INGEST_MAX_BYTES` (default 10 MiB). | `api/limits.py`; `api/routers/ingest.py` (`_ingest_max_bytes`) | Confusing **413** behavior depending on path; not wrong, easy to misconfigure. | Document both in one place or align defaults. |
| **P3** | **Chroma `connect()` always attempted** even when Neo4j optional; failure leaves `vector_store` unset. | `api/connections.py` (lines 66–71) | Expected graceful degradation; logs should show the failure (exception logged). | None required; ensure dashboards alert on log pattern if live mode expected. |

**Confirmed vs hypothesis**

- **Confirmed in code**: Chroma 1.x `HttpClient`, `hnsw:space` metadata, `/api/v2/heartbeat`, image pins, `chromadb>=1.5.6,<2`.
- **Hypothesis / needs runtime check**: Chroma image always includes `curl` for Docker healthchecks (compose + nightly); if a custom image omitted `curl`, healthchecks could fail (environment-specific).

---

## Chroma 1.x vs older assumptions

- **Client**: `chromadb.HttpClient` + `Settings(anonymized_telemetry=False)` — typical 1.x client API (`aria/retrieval/vector_store.py`, lines 38–46).
- **Collection**: `get_or_create_collection(..., metadata={"hnsw:space": "cosine"})` — HNSW space metadata (lines 44–46).
- **Heartbeat**: `http://{host}:{port}/api/v2/heartbeat` in `api/readiness.py` (lines 31–34), matching `docker-compose.yml` and nightly service health.
- **Version alignment**: `pyproject.toml` pins `chromadb>=1.5.6,<2`; Docker/CI use `chromadb/chroma:1.5.6` — consistent (not `latest`).

No in-repo references to 0.5.x or `/api/v1/heartbeat` were found; upgrade drift risk is mainly external (if someone ran an old Chroma server against this client).

---

## Neo4j + ingestion (dedup, graph, load)

- **Dedup**: In-memory set + optional `neo4j_dedup` with `IngestionRecord` MERGE (`aria/ingestion/pipeline.py`, `aria/graph/ingestion_record.py`). Documented partial-failure behavior: graph can succeed, vectors fail; tests note MERGE idempotency (`tests/eval/test_safety_reliability.py`).
- **Graph writes**: `write_payload` — single transaction, MERGE nodes/edges (`aria/graph/builder.py`, lines 64–97). **Cypher injection**: ingestion helpers use fixed queries + parameters for merge keys; not arbitrary user Cypher from HTTP for these paths.
- **Telemetry load**: `TelemetryStore` uses SQLite WAL, `check_same_thread=False`, `threading.Lock`, `busy_timeout=5000` (`aria/observability/telemetry_store.py`, lines 69–80). Under high concurrent writes, SQLite remains a bottleneck; Neo4j/Chroma are separate — telemetry DB growth and lock contention are the main coupling with “load” in this repo.

---

## Docker Compose & env

- **Pinned images**: `neo4j:5.26.2-community`, `chromadb/chroma:1.5.6` (`docker-compose.yml`, lines 4, 21); nightly matches Neo4j/Chroma tags.
- **Default password**: `NEO4J_AUTH` uses `aria_dev_password` default; comments warn local-only (`docker-compose.yml`, lines 8–10; `.env.example`, line 1).
- **Profile `full`**: `api` service with `profiles: [full]` (`docker-compose.yml`, lines 32–43); README line 74 matches (`docker compose --profile full up -d`).
- **`.env.example`**: Documents Neo4j, Chroma, API, placeholder mode, telemetry DB path, and unauthenticated `/metrics` and `/telemetry` — useful for production checklist; README should be aligned (see P3).

---

## Failure-mode matrix

| Scenario | Symptom | Mitigation |
|----------|---------|------------|
| **`NEO4J_PASSWORD` unset** with default Neo4j container | `/ready` neo4j OK, app **no Neo4j** | Unify defaults or require password; set `.env` explicitly |
| **Wrong `CHROMA_HOST` / port** | `vector_store` None; live query **503** `missing_dependencies` | Fix env; check `CHROMA_PORT` mapping in compose |
| **Chroma down after startup** | Stale client in `app.state`; queries fail at runtime | Restart API or add reconnect (not implemented — hypothesis for resilience) |
| **High `/ready` probe rate** | Extra Bolt connections | Tune probes; cache or reuse driver |
| **Many `IngestionRecord` nodes** | Slow dedup hydration | Pagination / pruning strategy |
| **Multi-worker ingest without `neo4j_dedup`** | Duplicate processing | Pass `neo4j_dedup` or single worker |

---

## Test gaps

- **No test** found that asserts **`NEO4J_PASSWORD` default alignment** between readiness and `connect_app_dependencies` (regression risk for P1).
- **Integration tests** for ingestion use **mocked** Neo4j for dedup (`tests/integration/test_ingestion_pipeline.py`); **live** Neo4j dedup/hydration volume is not stress-tested.
- **Security test** `test_chromadb_image_is_pinned_not_latest` only checks `docker-compose.yml`, not `nightly.yml` (nightly is pinned in practice — coverage gap, low risk).

---

## Recommended next steps (ordered, smallest first)

1. **P1** — Align `NEO4J_PASSWORD` handling between `api/readiness.py` and `api/connections.py` (same default or explicit “must set if URI set”).
2. **P3** — One-line README fix for which routes stay unauthenticated when `API_KEY` is set.
3. **P2** — Document multi-worker / HTTP ingest limitations for dedup and full pipeline (README or OpenAPI descriptions).
4. **P2** — Optional: reduce `/ready` Neo4j connection churn (reuse driver or throttle).

---

## Out of scope but related

Generic API auth surface (`api/deps.py`), SQLite telemetry retention/backup, and LLM configuration — not expanded in this document unless a follow-up pass is requested.
