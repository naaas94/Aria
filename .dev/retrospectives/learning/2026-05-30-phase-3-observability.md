# Learning retrospective — Phase 3 observability

**Date:** 2026-05-30  
**Task:** `phase-3-observability` — close MVP pickup gaps **G5** (HTTP/graph/LLM-cost Prometheus metrics + pipeline `INGESTION_DURATION`) and **G6** (replace silent SQLite swallows in the LLM client with warning + `aria_telemetry_write_errors_total{source="llm"}`), plus store-only `cost_by_request`, Ollama zero-cost docs, and unit tests.  
**Produced:** Ten implementation commits T1–T8 (`a140945` … `a247cfe`), docs T7 (`4fd0df8`, `fef97b0`), closure `a6849a2` with plan v1.1 §8; audit **pass-with-conditions** (`.dev/audits/2026-05-30-phase-3-observability.md`); no architectural-tier decision logs (plan §2). Verification: **56 passed** on Phase 3 test surface at implementation SHA.

**Why this qualified:** Observability is a cross-cutting seam (SQLite store, Prometheus registry, HTTP middleware, graph client, ingestion pipeline, LiteLLM cost semantics). The plan resolved five CONDITIONAL flags up front (label cardinality, rollup surface, test coverage for G6, doc targets). Outcome was clean on first audit—worth capturing what “done” means for metrics work versus eval honesty (Phase 2) or live wet runs (Phase 1).

---

## 1. Task context

Phase 3 followed pre-plan exploration at scout SHA `ee870022` (context map **CONDITIONAL** on HTTP `path` labels, pipeline vs HTTP `format` values, store-only vs `/telemetry` JSON for per-request cost, missing G6 tests, README vs `.env.example`). The orchestrator froze three metric definitions in §2, rejected HTTP `path` labels (aligns with `.dev/telemetry-audit.md`), kept pipeline `pdf`/`html` distinct from smoke `text`/`file`, and scoped rollup to `TelemetryStore.cost_by_request` without touching `GET /telemetry`.

Execution DAG: define metrics (T1) → parallel wire sites T2–T5 → parallel store rollup + docs T6/T7 → tests T8 → closure §8. All subtasks were `standard` or `trivial`; no decision logs required. `MVP_PICKUP.md` §191–195 checkboxes remain unchecked—explicitly deferred to Phase 5 hygiene (audit P3-F03).

---

## 2. What I now understand that I didn't before

### G5 and G6 are different failure classes

**G6** is integrity of the *persistence path*: SQLite write failures must not disappear. The fix is not “more metrics” but copying an existing envelope—warning with exception type only, `TELEMETRY_WRITE_ERRORS_COUNTER` with a new `source` label, Prometheus counters *outside* the SQLite `try`. **G5** is *signal completeness*: operators could see request counts and LLM call counts but not latency distributions or accumulated USD. Confusing them leads to “add a histogram” when the real bug is `except Exception: pass`.

### Prometheus placement follows a house pattern

In Aria, **SQLite writes go inside `try`; Prometheus observe/inc goes after**, even when the try only wraps the store call (`aria/agents/base.py`, post-fix `aria/llm/client.py`). G6 on the LLM path means: if SQLite fails, you still increment `LLM_CALL_COUNTER`, `LLM_CALL_DURATION`, and optionally `LLM_COST_COUNTER` on success—telemetry store loss does not hide LLM activity from Prometheus. That split is deliberate: TSDB remains the SLO surface; SQLite is the audit trail.

### Cardinality is a design choice, not an implementation detail

The scout map flagged `path_to_release.md` wanting method+path vs `telemetry-audit.md` praising counters without path. Phase 3 chose **`method` + `status_code` only** for `aria_http_request_duration_seconds`. That is not laziness—it is locking an ops contract before executors add labels. High-cardinality paths are a one-way door in Prometheus; resolving it in §0 saved a re-plan mid-T3.

### One histogram, two ingest vocabularies

`INGESTION_DURATION` is a **shared object** between HTTP smoke (`api/routers/ingest.py`, `format=text|file`) and full pipeline (`ingest_document`, `format=pdf|html`). Unifying label values would have been a breaking semantic change. The plan’s Flag 1 resolution—“no label unification”—is the correct mental model: same metric name, different label *values* for different entry points. Dashboards must filter by `format`, not assume one enum.

### Pipeline duration is a placement puzzle, not a one-liner

The highest re-plan risk (plan §5.3) was real: `ingest_document` has PARSE_ERROR, SKIPPED_DUPLICATE, and success paths. Timer starts **after** successful parse; observe only on final success return. Parse failures must not skew latency; duplicate skips must not increment the histogram. That is the same class of problem as eval golden early-exits (Phase 2)—control flow dominates observability correctness more than the Prometheus API.

### Store-only rollup vs operator JSON

Flag 3 was the fork: expose per-request cost on `GET /telemetry` or add SQL only. **Store-only** satisfies “optional rollup” in MVP pickup without breaking `tests/test_telemetry_endpoints.py`. I now read “optional” in roadmap docs as “may exist without being on the hot API path.” Scripts and future tooling can call `cost_by_request`; HTTP contract stays frozen.

### Ollama `cost_usd=None` is three different truths

1. **SQLite row:** `cost_usd` NULL  
2. **`GET /telemetry`:** `total_cost_usd` can be 0 for local-only deployments  
3. **Prometheus:** `aria_llm_cost_usd_total` not incremented when LiteLLM returns no `response_cost`  

Documenting in **both** README and `.env.example` (Flag 5: “or” → both) prevents “I fixed the bug in one place.” Operators otherwise file false defect reports against expected zero cost.

### Import order registers metrics

`prometheus_client` registers at import time. New constants in `metrics.py` only appear on `/metrics` after something imports them. Middleware importing `HTTP_REQUEST_DURATION` on app startup is load-bearing (plan §5.2 #5)—not boilerplate.

### `Counter.inc(float)` for fractional USD

`LLM_COST_COUNTER.inc(cost)` uses float increments; tests lock fractional behavior. Prometheus naming strips `_total` in some client accessors (`aria_llm_cost_usd` vs `aria_llm_cost_usd_total`)—tests must use the helpers the codebase already has (`_counter_value`), not raw string guesses.

### First-pass audit pass ≠ “trivial phase”

Phase 3 got **pass-with-conditions** without an amendment track (unlike Phase 2’s fail → CI wiring → re-audit). That reflects tighter §2 freezing and disjoint file touches, not that observability is easy. Minor gaps (mixed null/non-null `cost_usd` rows per `request_id`, no spy on `latency_ms/1000.0`) were **documented deferrals**, not oversights the auditor missed.

---

## 3. Decisions I would make again

**Resolve all five CONDITIONAL flags in plan §0 before packets.** Label policy, rollup surface, G6 test requirement, and dual-doc target were decided once; executors did not re-open cardinality during T3.

**T1 before all wire sites.** Frozen histogram buckets and label arrays in §2 avoided registration collisions and mid-flight renames.

**Parallel T2–T5 after T1.** Four domains (`llm`, middleware, graph, pipeline)—no file overlap, shorter wall time, smaller blast radius per commit than one mega “instrument everything” diff.

**Reject `/telemetry` JSON change for rollup (plan §5.1 Alternative C).** Right trade for MVP: SQL helper now, API later when contract and tests are intentional.

**G6 pattern verbatim from middleware/agents.** `source="llm"`, same warning shape, no traceback—alerts and log parsers stay consistent.

**T6/T7 parallel with T1 chain.** Rollup and docs do not need metric symbols; planning allowed early start.

**CHANGELOG coverage-gap deferrals.** Explicit “deferred to T8” / “deferred” rows beat silent omission; auditor treated them as accepted scope, not narrative concealment.

**Generalizable principle:** For observability work, **freeze metric schemas in the plan like API types**—names, labels, buckets, and unit conversions (`latency_ms / 1000.0`) are contracts; wire tasks are mechanical if contracts are copy-pasteable.

---

## 4. Decisions I would change

**Sync `MVP_PICKUP.md` G5/G6 checkboxes at closure commit.** Code and tests closed the gaps; leaving §191–195 unchecked (P3-F03) creates a permanent “is Phase 3 done?” ambiguity for future-me scanning the pickup doc. Phase 5 hygiene is reasonable for *architecture folder* updates, not for the primary gap table that motivated the phase.

**Plan §4 T8 file list: allow “existing or new unit file per domain.”** Landed `tests/unit/test_graph_client.py` outside the three listed files (P3-F02)—equivalent coverage, avoid prediction-divergence noise. Phase 1 taught the same lesson for serve/ingest/status tests.

**One extra `cost_by_request` test for mixed NULL and non-NULL rows.** SQL `SUM` ignores NULLs; behavior is standard but not asserted—cheap insurance when operators trust rollup for billing-ish views.

**Optional: spy HTTP histogram unit conversion in middleware test.** Deferred in CHANGELOG; seconds vs milliseconds mistakes are common and silent in sum-only histogram tests.

**Underlying errors:** Treating pickup checkboxes as “documentation debt” because the *plan* said Phase 5; **optimistic closure** on orchestrator artifacts while roadmap state lags.

**Better rule:** Any phase motivated by a numbered gap in `MVP_PICKUP.md` should flip those checkboxes (or strike them with a link to CHANGELOG) in the same closure PR as plan §8.

---

## 5. Patterns in my own thinking

**Equated “no architectural tier” with “low learning value.”** Phase 3 had no decision logs and passed audit first time—I could have skipped this retrospective. The seam surface (six coupling surfaces in the audit) was still dense; the learning is in *telemetry semantics*, not process drama.

**Trusted adversarial §5.3 on T5 without re-reading `pipeline.py` myself.** Appropriate when executors halt on ambiguity; for timer placement I should still spot-check the completion path once—same control-flow instinct as Phase 2’s early returns.

**Accepted deferred tests because audit passed.** Documented gaps (P3-F04, P3-F05) are fine for merge; I should decide per gap whether “documented only” is acceptable for *money-adjacent* signals (`cost_by_request`) vs *nice-to-have* (observe arg spy).

**Compared Phase 3 favorably to Phase 2 and underweighted pickup sync.** Process improved; **roadmap truth** did not—same class of drift as Phase 1’s sign-off vs §8-at-HEAD, but smaller.

**Did not revisit whether middleware should still `except Exception: pass` on the whole telemetry block.** G6 fixed LLM; HTTP middleware pre-existed. Out of scope, but easy to assume “observability phase” closed all swallow patterns—it did not.

---

## 6. Open questions

- When should `cost_by_request` surface on `GET /telemetry` or CLI—and what JSON shape avoids breaking existing consumers?
- Do alert rules need updating for `source="llm"` on `aria_telemetry_write_errors_total`, or is `source=~".+"` already the norm?
- Should pipeline `INGESTION_DURATION` ever observe SKIPPED_DUPLICATE latency separately (operator question, not MVP)?
- After Phase 5 hygiene, does `.dev/telemetry-audit.md` need a refresh pass linking to the new histograms and G6 closure?
- Multi-worker SQLite + Prometheus global registry: what breaks first under load—store busy timeout or scrape cardinality?

---

## 7. Single paragraph synthesis

Phase 3 taught me that **observability “completeness” in this codebase is mostly about honoring two contracts at once**: Prometheus labels and buckets frozen like public types, and SQLite failures made visible without starving the TSDB path. G6 and G5 are not the same work—swallows are integrity bugs, missing histograms are operator blind spots. The hardest implementation risk was not the Prometheus API but **where in `ingest_document` time starts and stops**. Pickup-doc checkboxes and `/telemetry` JSON were deliberately left behind for hygiene and contract safety; the code at `a247cfe` is the source of truth until I sync the roadmap. The compounding lesson across Phases 1–3: **green tests and a pass-with-conditions audit do not update `MVP_PICKUP.md` for you**—if the phase exists because of a gap table, closure must update that table or future sessions will re-plan work that already shipped.
