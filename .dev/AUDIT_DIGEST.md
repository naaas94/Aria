# Audit digest — validated findings and action plan

**Date:** 2026-04-09
**Source reports:** `api-contracts-errors-auth-audit.md`, `telemetry-audit.md`, `evaluation_ci_audit.md`, `product-architecture-audit.md`, `infrastructure-data-dependencies-audit.md`
**Validation:** All P0/P1 findings confirmed against codebase (code-level cross-reference, not just report claims).

---

## P0 — CI is broken

[FIXED]         These are currently failing or will fail on the next CI run.

        ### 1. OpenAPI path expectations are stale

        `/metrics` and `/telemetry` exist in the app (`api/main.py` lines 145–146, `api/routers/telemetry.py`) but are missing from:
        - `tests/eval/test_security_audit.py` → `test_documented_openapi_paths_match_expected_set` (lines 103–111)
        - `tests/eval/golden_set/cases/security/openapi_paths.yaml` → `expected_paths` (lines 9–17)

        **Fix:** Add `/metrics` and `/telemetry` to both expected-path sets.

### 2. Medium-tier retrieval goldens fail

All five files under `tests/eval/golden_set/cases/retrieval/` set `retrieved_context: ""`. The retrieval lens (`run_retrieval_check` in `runner.py`) checks keyword hits against `expected_components` — empty context means zero hits, guaranteed failure.

Nightly step "Golden set (all tiers)" runs `--golden-tier=slow` which includes `medium`, so nightly is red.

**Fix (pick one):**
- Populate `retrieved_context` with deterministic synthetic text matching `expected_components`.
- Switch to `expect.replay` with committed fixtures.
- Mark cases `skip` / quarantine until wired to real retrieval.

---

## P1 — Must fix (security, correctness, misleading behavior)

[FIXED]         ### 3. `NEO4J_PASSWORD` default mismatch

        | Location | Default |
        |----------|---------|
        | `api/readiness.py` line 19 | `"aria_dev_password"` |
        | `api/connections.py` line 56 | `""` (empty string) |

        If `NEO4J_URI` is set but `NEO4J_PASSWORD` is unset, `/ready` reports `neo4j: true` while the app never obtains a driver — misleading readiness.

        **Fix:** Same default in both files, or require explicit password when `NEO4J_URI` is set (fail fast).

[FIXED]         ### 4. `A2AClient` never sends `X-A2A-Secret`

        `aria/protocols/a2a/client.py` `delegate_task` (lines 59–63) does a plain `httpx.post` with no auth header. The server (`aria/protocols/a2a/server.py` lines 24–35) enforces `X-A2A-Secret` when `A2A_SHARED_SECRET` is set → secured peer agents always 401.

        **Fix:** Read `A2A_SHARED_SECRET` from env and attach `X-A2A-Secret` header in `delegate_task`. Add test: 401 without header, 200 with it.

[FIXED]         ### 5. `/metrics` and `/telemetry` are unauthenticated even when `API_KEY` is set

        `api/main.py` mounts `telemetry.router` without `require_api_key_when_configured`. `/telemetry` JSON includes `requests.by_path` — operational intelligence useful for reconnaissance.

        **Fix (at least one):**
        - Network policy: bind localhost, reverse proxy auth, firewall.
        - env-gated auth on observability routes.
        - Document the exposure explicitly and accept the risk for internal-only deployments.

[FIXED]         ### 6. Documentation says "all routes except `/health`" are gated — wrong

        | Source | Claim |
        |--------|-------|
        | `.env.example` line 20 | "on all routes except `/health`" |
        | `README.md` ~line 116 | Same |
        | Reality | `/health`, `/ready`, `/metrics`, `/telemetry` are all unauthenticated |

        **Fix:** Update `.env.example` and `README.md` to list all unauthenticated routes explicitly.

[FIXED]        ### 7. Nightly runs golden tests twice, overwrites reports

        `.github/workflows/nightly.yml`: step "Golden set (all tiers, with eval store)" runs `pytest tests/eval/golden_set/test_goldens.py`, then step "Full eval suite" runs `pytest tests/eval/` which includes `golden_set/` again. Second run overwrites `golden_report.json` / `.xml`.

        **Fix:** Exclude `golden_set` from the second invocation (`--ignore=tests/eval/golden_set`)

### 8. `requires_multi_hop` flag is a no-op

`tests/eval/golden_set/runner.py` lines 198–200: when `spec.requires_multi_hop` is set, it only writes `sub["multi_hop_declared"] = True` — no actual validation of multi-hop retrieval.

**Fix:** Either implement a real check (trace metadata, hop count) or remove/rename the flag to avoid false confidence.

### 9. GraphRAG vs vector benchmark uses synthetic data

`scripts/benchmark_retrieval.py` feeds two hardcoded strings into `score_retrieval`; scoring is lexical keyword matching (`tests/eval/graphrag_vs_vector_rag.py` lines 86–88). Not evidence of live retrieval quality.

**Fix:** Add a clear "methodology stub" label in the script header. For real decisions, use `tests/eval/e2e/test_live_queries.py` with a seeded graph, or wire the script to call actual retrievers behind a flag.

---

## P2 — Should fix (reliability, operational quality)

[FIXED]        ### 10. Silent error swallowing in telemetry and agent paths

        - `api/middleware_telemetry.py` lines 50–51: `except Exception: pass` — SQLite write failures, Prometheus counter failures, all silently dropped.
        - `aria/agents/base.py`: `record_agent_execution` failures swallowed; Prometheus still increments after → SQLite and Prometheus can diverge.

        **Fix:** Replace `pass` with `logger.warning(...)` (exception type, no stack spam). Optionally add `aria_telemetry_write_errors_total` counter.

[FIXED]        ### 11. No retention / pruning for telemetry SQLite

        `aria/observability/telemetry_store.py` has `INSERT` and `SELECT` only — no `DELETE`, no time-based pruning, no `VACUUM`. Long-running production → unbounded disk growth.

        **Fix:** Document a retention cron (`DELETE FROM http_requests WHERE ts < datetime('now', '-N days'); VACUUM;`) or implement in-app periodic trim.

[FIXED]        ### 12. 413 and 422 error body inconsistencies

        - `api/middleware_body_limit.py` returns `{"detail": "..."}` with no `code` field (unlike all `HTTPException`-based errors which include `code`).
        - `HTTPException` `code_map` in `api/main.py` (lines 99–105) lacks 413 and 422 — both fall through to generic `"http_error"`.
        - Telemetry invalid `since` returns a plain-string 422 body, not Pydantic validation shape.

        **Fix:** Add `"code": "payload_too_large"` to middleware 413 JSON. Extend `code_map` for 413 and 422.

[FIXED]        ### 13. Multi-worker / multi-instance deployment not documented

        - In-process `_ingested_hashes` set is per-process (`aria/ingestion/pipeline.py`).
        - SQLite telemetry is single-writer under concurrent load.
        - Multiple instances with local DB paths → fragmented data.

        **Fix:** Document multi-worker requirements in README or ops runbook: use `neo4j_dedup`, single writer for telemetry, shared volume or external store for HA.

[FIXED]        ### 14. `/ready` creates new Neo4j + Chroma connections per probe

        `api/readiness.py` opens fresh Bolt and HTTP connections per request instead of using `app.state.connections`.

        **Fix:** Reuse pooled driver from `app.state` or cache probe results with a short TTL.

[FIXED]        ### 15. `list_complete_content_hashes` loads all hashes unbounded

        `aria/graph/ingestion_record.py` — no pagination or cap. After many ingestions, startup hydration becomes slow and memory-heavy.

        **Fix:** Paginate or cap; implement incremental sync if hash count grows large.

[FIXED + noted on dev ingest only]    ### 16. HTTP `/ingest/text` is not the full pipeline

    `api/routers/ingest.py` only chunks text — no graph writes, no vector store, no dedup. Operators may assume it drives the full pipeline.

    **Fix:** Clarify in API description / README, or wire optional full pipeline behind a flag.

### 17. Orchestration traces not persisted to telemetry

        `OrchestrationGraph.execute` produces `ExecutionResult.traces` but doesn't call `TelemetryStore.record_agent_execution` — that path is `BaseAgent.run()` only. Dashboards may under-count agent work.

        **Fix:** If needed for product, emit one telemetry row per `ExecutionResult` at the API boundary that runs the graph.

### 18. CI step label says "includes replay" — no replay cases exist

`.github/workflows/ci.yml` job name mentions replay, but `replay/` only contains `.gitkeep` and no YAML case uses `expect.replay`.

**Fix:** Rename CI step or add a minimal replay golden once fixtures exist.

### 19. Nightly runs Python 3.12 only; PR CI tests 3.12 + 3.13

`.github/workflows/nightly.yml` pins 3.12; `ci.yml` matrix includes 3.13.

**Fix:** Add 3.13 to nightly or accept the gap.

### 20. LangGraph reference has stub nodes, no tests

`aria/orchestration/langgraph_reference/nodes.py` uses `_NoopTools` and stub implementations. No tests import `build_langgraph()`.

**Fix:** Add optional smoke test (`pytest.mark.skipif` for missing dep) or a single doc sentence clarifying stubs.

[FIXED]        ### 21. `test_security_audit` references non-existent `docs/security_audit_report.md`

        Assertion message in `tests/eval/test_security_audit.py` mentions this file; it doesn't exist in the repo.

        **Fix:** Add the doc or fix the assertion message.

---

## P3 — Minor (polish, low risk)

[all fixed]        | # | Finding | Fix |
        |---|---------|-----|
        | 22 | Two upload limits: `ARIA_MAX_INGEST_BODY_BYTES` (12 MiB) vs `INGEST_MAX_BYTES` (10 MiB) | Document both in one place or align defaults |
        | 23 | `StepTrace.error` duplicates `state.error` on every trace after first failure | Record error only on transition into error state |
        | 24 | Prometheus `model` / `agent_name` / `tool_name` labels could grow cardinality | Monitor label sets; consider allowlist |
        | 25 | `complete_structured` repair path records two `llm_calls` rows for same `request_id` | Document or add a `phase` field |
        | 26 | Eval store writes raw `case.input` to JSONL with no scrubbing (unlike `recorder.py`) | Document "no secrets in goldens"; optionally reuse scrub helper |
        | 27 | Golden security `check_type` handlers duplicate `test_security_audit.py` logic | Extract shared helper or single source of truth for expected path sets |
        | 28 | Graph column contract tests only lock `impact_by_regulation` | Add tests for other stable named queries or document scope |
        | 29 | `slow` tier: no case uses `tier: slow`; `--golden-tier=slow` means "all tiers" | Add true slow cases or document semantics |
        | 30 | 500 handler returns opaque error; could include request ID | Optional: include `request_id` in error JSON for client traceability |

---

## Recommended execution order

### Sprint 1 — Unblock CI + fix security/correctness (P0 + P1)

| Order | Item | Effort | Files touched |
|-------|------|--------|---------------|
| 1 | **#1** Add `/metrics`, `/telemetry` to expected-path sets | XS | `test_security_audit.py`, `openapi_paths.yaml` |
| 2 | **#2** Fix or quarantine retrieval goldens | S | `cases/retrieval/*.yaml` |
| 3 | **#3** Align `NEO4J_PASSWORD` defaults | XS | `readiness.py`, `connections.py` |
| 4 | **#6** Fix doc claims about unauthenticated routes | XS | `.env.example`, `README.md` |
| 5 | **#7** Deduplicate nightly golden run | XS | `nightly.yml` |
| 6 | **#4** Wire `X-A2A-Secret` in `A2AClient` | S | `a2a/client.py`, new test |
| 7 | **#12** Add `code` to 413 middleware + extend `code_map` | XS | `middleware_body_limit.py`, `main.py` |
| 8 | **#10** Replace silent `pass` with warning log | XS | `middleware_telemetry.py`, `agents/base.py` |

### Sprint 2 — Operational hardening (P2)

| Order | Item | Effort |
|-------|------|--------|
| 9 | **#11** Telemetry retention strategy | S |
| 10 | **#5** Decide telemetry auth policy (code or ops) | S |
| 11 | **#13** Document multi-worker requirements | S |
| 12 | **#14** Reuse pooled driver in `/ready` | S |
| 13 | **#8** Remove or implement `requires_multi_hop` | S |
| 14 | **#9** Label benchmark script as methodology stub | XS |
| 15 | **#18** Rename CI step / remove "replay" label | XS |

### Backlog (P2 low-urgency + P3)

Items 15–30: schedule as capacity allows. None block releases; all reduce tech debt or improve consistency.

---

## Cross-cutting themes

1. **Observability routes are a security surface** — three reports independently flagged `/metrics` and `/telemetry` exposure. Needs a single architectural decision (network-only vs app-level auth) documented once.
2. **Error contract drift** — 413 middleware, 422 telemetry, and `HTTPException` catch-all produce inconsistent JSON shapes. One pass through the error layer fixes all three.
3. **Telemetry store is a single-node tool** — no retention, no multi-writer story, silent failure. Fine for dev; needs ops guardrails for production.
4. **Golden set has structural gaps** — empty retrieval context, no-op multi-hop flag, no replay cases, stale path sets. A focused session fixes the suite.
5. **Documentation lags code** — `.env.example`, `README.md`, CI step names, and assertion messages reference outdated states. Small fixes, high trust impact.
