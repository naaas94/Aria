# API contracts, errors, and authentication — QA audit

**Topic:** API surface, contracts, errors, authentication (`require_api_key_when_configured`), public vs protected routes.  
**Date:** 2026-04-09  
**Scope:** Python/FastAPI (`api/`), domain (`aria/`), tests (`tests/eval/`, `tests/unit/`), config (`.env.example`).

**Tests run (local):** `python -m pytest tests/eval/test_api_contracts.py -q` — 26 passed (Chroma/OpenTelemetry deprecation warnings only). Full CI not verified.

---

## Executive summary

- **Contracts & tests:** `tests/eval/test_api_contracts.py` covers core REST shapes, MCP tool schemas vs Pydantic, `impact_by_regulation` column aliases, A2A cards vs `AGENT_CARDS`, and schema-version defaults — but documents that `schema_version` is not globally enforced unless `ARIA_STRICT_SCHEMA_VERSION` is used (separate unit tests). **Drift risk:** OpenAPI path inventories in `test_security_audit` and `test_openapi_includes_core_paths` omit `/metrics` and `/telemetry`.
- **Errors:** Global handlers in `api/main.py` unify most failures behind `detail` + `code`; **500** uses generic `ErrorBody` and logs stack traces server-side. **Gaps:** `LimitIngestBodySizeMiddleware` returns **413 without `code`**, and many `HTTPException` status codes fall through to **`code: "http_error"`** (e.g. 413, 422 from telemetry).
- **Auth:** `require_api_key_when_configured` gates ingest, query, impact, and agents when `API_KEY` or `ARIA_API_KEY` is set; **`/health`, `/ready`, `/metrics`, `/telemetry` are intentionally public** (see `api/main.py`, `.env.example`). Startup logs a **warning** if no API key is configured.
- **Top production risks:** (1) Unauthenticated telemetry/metrics on a network-exposed host; (2) default open API when no key is set; (3) error body inconsistency (413 middleware vs HTTPException path); (4) placeholder/live behavior via `ARIA_PLACEHOLDER_API`.

---

## Scope map

| Area | Primary locations |
|------|-------------------|
| App bootstrap, CORS, lifespan, exception handlers | `api/main.py` |
| API key dependency | `api/deps.py` |
| Error models / 422 payload | `api/errors.py` |
| Body size limit (413) | `api/middleware_body_limit.py`, `api/limits.py` |
| Telemetry & Prometheus | `api/routers/telemetry.py`, `api/middleware_telemetry.py` |
| Contracts & schema versions | `aria/contracts/impact.py`, `aria/contracts/regulation.py`, `aria/contracts/_strict.py` |
| Named graph queries & column aliases | `aria/graph/queries.py` |
| MCP I/O | `aria/protocols/mcp/tools.py`, `aria/protocols/mcp/server.py` |
| A2A cards / envelopes | `aria/protocols/a2a/agent_card.py`, `aria/protocols/a2a/server.py` |
| Contract tests | `tests/eval/test_api_contracts.py` |
| Auth / route inventory tests | `tests/eval/test_security_audit.py`, `tests/conftest.py` |
| Telemetry endpoint tests | `tests/test_telemetry_endpoints.py` |
| Strict schema tests | `tests/unit/test_contract_strict.py` |
| Config / env docs | `api/config.py`, `.env.example` |

---

## Findings

| Sev | Finding | Evidence | Impact | Recommendation |
|-----|---------|----------|--------|----------------|
| **P1** | `/metrics` and `/telemetry` are not protected by API key when `API_KEY` is set — same pattern as `/health`/`/ready`. | `api/main.py` (telemetry router without `_route_auth`); `.env.example` L46–48. | Prometheus text and JSON aggregates readable to anyone who can reach the port — operational and possibly sensitive usage disclosure. | Edge/network policy (bind localhost, reverse proxy auth) or optional env to require key on observability routes. |
| **P1** | `.env.example` says API key applies to “all routes except `/health`” — incomplete. | `.env.example` L20–21 vs `api/main.py` + telemetry. | Operators may misconfigure production. | Doc fix: list `/ready`, `/metrics`, `/telemetry` explicitly. |
| **P2** | 413 from body-limit middleware has no `code` field (unlike `HTTPException` path). | `api/middleware_body_limit.py` L26–32. | Clients expecting uniform `{detail, code}` may see inconsistent 413 bodies. | Add `code` (e.g. `payload_too_large`) to middleware JSON. |
| **P2** | `HTTPException` `code` mapping is partial; unlisted statuses become `"http_error"`. | `api/main.py` L99–105. | 413 (ingest), 422 (telemetry invalid `since`) share generic code with other cases. | Extend `code_map` for exposed statuses (at least 413, 422) or document catch-all. |
| **P2** | Telemetry invalid `since` uses `HTTPException(422)` — body is `{detail: str, code: "http_error"}`, not `validation_error` + error list. | `api/routers/telemetry.py`; `api/main.py` handler; `tests/test_telemetry_endpoints.py` asserts 422 only. | Inconsistent 422 shape vs Pydantic validation. | Align handler or document two 422 shapes. |
| **P2** | OpenAPI path inventories in tests omit `/metrics` / `/telemetry`. | `tests/eval/test_security_audit.py` L101–116; `tests/eval/test_api_contracts.py` `test_openapi_includes_core_paths`. | Silent drift: new public routes without security review. | Add paths to both tests. |
| **P3** | Graph column contract tests only lock `impact_by_regulation`. | `tests/eval/test_api_contracts.py`; other queries in `aria/graph/queries.py`. | Downstream/MCP consumers assuming other query shapes can break without test signal. | Add tests for stable named queries or document scope. |
| **P3** | `SCHEMA_VERSION` / `schema_version` informational unless strict env on. | `tests/eval/test_api_contracts.py`; `aria/contracts/_strict.py`; `tests/unit/test_contract_strict.py`. | Wrong `schema_version` not rejected unless `ARIA_STRICT_SCHEMA_VERSION` set. | Product decision: strict in prod or document risk. |
| **P3** | MCP `call_tool` wraps failures with generic message — no traceback to client (good). | `aria/protocols/mcp/server.py` L77–86. | Safer; debugging relies on logs. | Ensure log/PII policy at ops layer. |
| **P3** | 500 handler does not return exception text to clients. | `api/main.py` L124–135. | Opaque failures for API consumers; safer default. | Optional: include request id in JSON if useful. |

**Confirmed:** Catch-all `Exception` returns `ErrorBody(detail="An unexpected error occurred.", code="internal_error")` and logs traceback — no stack in JSON.

**Hypothesis (needs runtime verification):** `LimitIngestBodySizeMiddleware` only checks `Content-Length` for `POST` under `/ingest`; chunked uploads may bypass the limit.

---

## Failure-mode matrix

| Scenario | Symptom | Mitigation |
|----------|---------|------------|
| `API_KEY` unset on exposed host | Data-plane routes open; lifespan warning logged. | Set `API_KEY` / `ARIA_API_KEY`; network restrictions. |
| Key set but `/metrics`/`/telemetry` exposed | Unauthenticated scrape/JSON telemetry. | Firewall, bind address, or optional app-level auth. |
| Wrong Neo4j/Chroma URL or down | `/ready` 503 degraded; live routes may 503. | Monitor `/ready`, dependency health. |
| `ARIA_PLACEHOLDER_API=true` (default) | Synthetic `/query`/`/impact` with `X-ARIA-Mode: placeholder`. | Set `ARIA_PLACEHOLDER_API=false` for live behavior. |
| Multiple workers | Prometheus / SQLite telemetry assumptions may vary. | Validate deployment docs for multi-worker. |

---

## Test gaps

- `tests/eval/test_api_contracts.py`: missing `/metrics`, `/telemetry` in OpenAPI assertions.
- `test_security_audit.test_documented_openapi_paths_match_expected_set`: does not fail when observability routes are added — inventory gap.
- MCP tests: stub path; limited assertion on `error_code` for validation failures.
- `schema_version` “no assert in aria/” test (L338–350) is a deliberate canary for global gating.

---

## Recommendations (ordered, smallest first)

1. **P1 — Documentation:** Update `.env.example` to list all unauthenticated routes: `/health`, `/ready`, `/metrics`, `/telemetry`.
2. **P2 — Tests:** Add `/metrics` and `/telemetry` to `test_documented_openapi_paths_match_expected_set` and `test_openapi_includes_core_paths`.
3. **P2 — Error consistency:** Add `code` to `LimitIngestBodySizeMiddleware` 413 JSON; extend `http_exception_handler` `code_map` for 413 (and optionally 422).
4. **P1/P2 — Operations:** Decide if `/telemetry` JSON should be internet-public; if not, env-gated auth on telemetry router or mandatory edge protection.
5. **P3:** Add stability tests for additional `QUERIES` treated as external contracts, or document that only `impact_by_regulation` is contract-tested.

---

## Out of scope (related)

- A2A `A2A_SHARED_SECRET` on separate agent apps (`aria/protocols/a2a/server.py`).
- Multi-worker + SQLite telemetry store behavior.
- Cypher injection: mitigated by named queries (`execute_named_query`) — no arbitrary Cypher from MCP callers.

---

## Key code references

- Exception handlers and route auth: `api/main.py` (handlers ~L97–135, routers ~L138–146).
- API key dependency: `api/deps.py` (`require_api_key_when_configured`).
- 413 middleware (no `code`): `api/middleware_body_limit.py`.
- Public observability routes: `api/routers/telemetry.py` (`/metrics`, `/telemetry`).
- Env documentation: `.env.example` (API key, telemetry notes).
