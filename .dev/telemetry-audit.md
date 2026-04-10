# Telemetry QA / audit report

Audit focus: HTTP telemetry API (`/metrics`, `/telemetry`), security exposure, `TelemetryMiddleware`, `TelemetryStore` (SQLite), Prometheus metrics, LLM & agent wiring. Evidence from codebase as of audit date.

---

## Executive summary

- **Telemetry HTTP API**: `GET /metrics` exposes Prometheus text from the global registry; `GET /telemetry` returns a fixed nested JSON shape with `period`, `llm`, `requests`, `agents`, driven by `hours` (default 24) or `since` (ISO8601). Invalid `since` yields **422** via `HTTPException`, not FastAPI’s default validation body. **OpenAPI**: routes are defined on `APIRouter` with `Query` metadata and appear in docs when `openapi_url` is enabled (disabled in production via `is_production_deployment()`).
- **Security**: `telemetry.router` is mounted **without** `require_api_key_when_configured` (explicit comment in `api/main.py`); `.env.example` documents unauthenticated access and edge/proxy protection. **`GET /telemetry` aggregates include `requests.by_path`** — useful for ops, reconnaissance-relevant if exposed.
- **TelemetryMiddleware**: Skips `/health`, `/ready`, `/metrics`, `/telemetry`; **`RequestIDMiddleware` is registered after `TelemetryMiddleware`**, so on the inbound path request ID is bound **before** telemetry runs; latency is **wall time for `call_next`** (monotonic). **`except Exception: pass`** drops both SQLite writes and Prometheus increments with no log — observability can fail silently.
- **TelemetryStore**: **WAL**, **`busy_timeout=5000`**, **threading lock** around DB ops, **no retention/trim**, **no backup** in app. Suitable for **single-node** or **few writers**; **multi-worker** on one file is SQLite-typical (serialized writes); **multi-instance** needs a **shared** DB path (with caveats) or **accepts split brains** per instance.
- **Prometheus**: Naming is `aria_*`; **`aria_http_requests_total`** uses **`method` + `status_code` only** (no path). Other metrics are wired in ingest/query/graph/MCP/agent/LLM paths; **definitions exist** for full surface area covered by tests and code review.

---

## Scope map

| Area | Primary locations |
|------|-------------------|
| Routes | `api/routers/telemetry.py` |
| App wiring | `api/main.py` (`TelemetryMiddleware`, `include_router(telemetry.router)`, lifespan `get_telemetry_store` / `close_telemetry_store`) |
| HTTP middleware | `api/middleware_telemetry.py`, `api/middleware_request_id.py` |
| SQLite store | `aria/observability/telemetry_store.py` |
| Prometheus defs | `aria/observability/metrics.py` (import side-effect in `telemetry.py`: `import aria.observability.metrics  # noqa: F401`) |
| LLM hooks | `aria/llm/client.py` (`record_llm_call`, counters/histograms) |
| Agent hooks | `aria/agents/base.py` (`record_agent_execution`; silent `except` on store write) |
| Config docs | `.env.example` (`ARIA_TELEMETRY_DB`, commentary on auth) |
| Tests | `tests/test_telemetry_endpoints.py`, `tests/test_middleware_telemetry.py`, `tests/test_telemetry_store.py`, `tests/test_llm_telemetry.py`, `tests/test_agent_telemetry.py`, `tests/unit/test_metrics.py` |

---

## Findings

| Sev | Finding | Evidence | Impact | Recommendation |
|-----|---------|----------|--------|----------------|
| **P1** | **`/metrics` and `/telemetry` are intentionally unauthenticated** when `API_KEY` is unset; when set, they remain **outside** `require_api_key_when_configured`. | `api/main.py` (telemetry router without `_route_auth`); `.env.example` | Anyone who can reach the service gets Prometheus metrics and JSON aggregates (including **`by_path`**). | Treat as **must** for internet-facing: restrict by **network policy**, **reverse proxy**, or add an optional env-gated auth for observability routes (smallest change: document + enforce at edge first). |
| **P1** | **`GET /telemetry` exposes HTTP traffic shape** via `requests.by_path` counts. | `aria/observability/telemetry_store.py` (`telemetry_summary` → `by_path`) | Reconnaissance / usage profiling; not full PII but **operational intelligence**. | If sensitive, **redact/aggregate paths** (prefixes) or gate endpoint. |
| **P2** | **TelemetryMiddleware swallows all errors** on persist + counter increment. | `api/middleware_telemetry.py` (`except Exception: pass`) | DB full, lock errors, or bugs → **no row, no counter, no log** — breaks “telemetry as evidence” silently. | Log at **warning** once per error class or use **metrics** for failed writes; avoid failing the request. |
| **P2** | **Agent `record_agent_execution` failures are swallowed**; Prometheus still increments after. | `aria/agents/base.py` | **SQLite and Prometheus can diverge** for agents. | Align with middleware policy: log + optional counter `aria_telemetry_write_errors_total`. |
| **P2** | **No retention, pruning, or VACUUM** in application code. | `TelemetryStore` | Long-running prod → **unbounded disk** on default file DB. | P1 ops: **cron job** / sidecar to trim old rows or rotate `ARIA_TELEMETRY_DB`; document capacity. |
| **P2** | **Multi-worker / multi-instance** semantics are **not documented in code** beyond SQLite mechanics. | WAL + lock + single file path; global singleton `get_telemetry_store` | **N workers → one DB file** is OK for SQLite with contention; **N instances with local paths → N disjoint datasets**; **NFS/shared FS** has known SQLite caveats. | Document deployment assumptions; for HA consider external TSDB or centralized store. |
| **P3** | **Invalid `since` returns 422** with `HTTPException` detail string — shape differs from FastAPI validation errors for bad `hours`. | `api/routers/telemetry.py` (`_parse_since_iso`); `tests/test_telemetry_endpoints.py` | Clients must handle **two 422 styles** if they parse bodies. | Optional: unify with `Query` validation or document. |
| **P3** | **`period` embeds raw `since` string** for display. | `api/routers/telemetry.py` | Very long / weird query strings → odd `period` (cosmetic). | Cap length or normalize. |
| **P3** | **`complete_structured`** may call **`complete` twice** (repair path) → **two `llm_calls` rows** same `request_id`. | `aria/llm/client.py` | Aggregates count **HTTP-level LLM calls**, not “logical user operations.” | Document or add a correlation field / “phase” if needed. |
| **P3** | **Prometheus `aria_http_requests_total`** does not label **path** (good); **`model` / `agent_name` / `tool_name`** labels depend on **bounded enums** in practice. | `aria/observability/metrics.py` | Misconfiguration or dynamic model strings could grow cardinality. | Monitor label sets; consider allowlist in prod. |

---

## Failure-mode matrix

| Scenario | Symptom | Mitigation |
|----------|---------|------------|
| **`API_KEY` unset on public host** | Open `/metrics`, `/telemetry` | Set key **and** block observability at proxy, or extend auth to these routes |
| **Disk full / SQLite I/O error** | Middleware/agent store writes fail silently; HTTP still 200 | Monitoring on disk; structured log on write failure |
| **High concurrency writers** | SQLite **busy** (5s timeout), latency spikes | Reduce write volume, single writer process, or different store |
| **Multiple replicas, local DB path** | Each instance **different** SQLite file → **fragmented** JSON summary | Shared volume (with SQLite caveats) or external aggregator |
| **Wrong `ARIA_TELEMETRY_DB`** | Data written to unexpected path / cwd | Document default resolves under repo root (`telemetry_store._resolve_db_path`) |
| **LLM called outside HTTP request** (no `request_id`) | `request_id` stored as `""` | Correlation gap for batch jobs; tests expect empty id in some cases |

---

## Test gaps

- **No test** that **`except Exception: pass`** in middleware is observable (intentionally hard); **no test** for SQLite **busy** / **locked** behavior under load.
- **Middleware order** is **implied** by passing tests (`X-Request-ID` + DB row) but **not asserted** explicitly in a single test that documents Starlette ordering.
- **`GET /telemetry` error body** for invalid `since` **not asserted** (only status 422).
- **Multi-process / file locking** not covered (integration-heavy).
- **Agent error path** does not assert **`request_id`** when context is empty (only success path binds ID in test).

---

## Recommended next steps (ordered, smallest viable first)

1. **P1 — Ops/doc**: Add a short **runbook note**: restrict `/metrics` and `/telemetry` at **load balancer**; optional **`ARIA_TELEMETRY_DB`** per environment.
2. **P2 — Observability**: Replace bare **`pass`** in `TelemetryMiddleware` (and optionally `BaseAgent`) with **`logger.warning`** including exception type (no stack spam if noisy).
3. **P2 — Ops**: Define **retention** (SQL DELETE by `ts` + periodic VACUUM) or external backup — smallest is a **documented cron** + SQL one-liner.
4. **P3**: Decide whether **`by_path`** should be **coarser** (prefix) for untrusted networks.

---

## Out of scope (related)

`RequestIDMiddleware` assigns `response` after `call_next`; if `call_next` raises, that pattern may break — unrelated to telemetry store but affects whether `X-Request-ID` is always set on errors (not verified in this audit).

---

## Tests run (audit)

`pytest` on: `test_telemetry_endpoints`, `test_middleware_telemetry`, `test_telemetry_store`, `test_llm_telemetry`, `test_agent_telemetry`, `unit/test_metrics` — **38 passed** (local run at audit time). Re-run before release; do not assume CI green without pipeline evidence.
