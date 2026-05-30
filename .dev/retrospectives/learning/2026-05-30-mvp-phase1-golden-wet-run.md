# Learning retrospective — MVP Phase 1 golden wet run

**Date:** 2026-05-30  
**Task:** `mvp-phase1-golden-wet-run` — prove the Aria Phase 1 CLI golden path on a live stack (Neo4j, Chroma, real LLM), fix pre-run blockers, execute the session, close audit findings, and mark the orchestrator plan complete.  
**Produced:** Eight executor commits (T1–T8), wet run log in `.dev/MVP_PICKUP.md`, architectural decision log `.dev/decision-logs/T6-wet-run.md`, audit (fail → pass after amendment), plan v1.1 with §8 handoff, ~1.1k lines of diff across CLI, fixtures, tests, and `.dev/` artifacts. Closure SHAs: code at `5df123f`, documentation at `19e35ca`.

**Why this qualified:** One **architectural** subtask (the live golden-path session), a full contract-first orchestrator cycle (pre-plan map → plan → packets → execution → adversarial audit → amendment → re-audit), and several concepts that only became concrete after running the stack—not after reading the plan.

---

## 1. Task context

The work was scoped in `.dev/plans/mvp-phase1-golden-wet-run/plan.md`: five parallel prep tasks (sample HTML fixture, pytest integration markers, serve port vs Chroma, regulation IDs after ingest, status/ingest LLM messaging), then a single live session exercising `docker compose` → `aria init` → ingest → query → impact → telemetry → optional serve/`/ready` → integration pytest, with `ARIA_PLACEHOLDER_API=false`.

The session **signed off Y** with documented caveats (Chroma compose health flaky, impact chain empty after ingest-only sample, no code fixes needed). An initial audit at `d448a31` **failed** on contract drift (unit tests added despite plan text forbidding them, plan still "Active", context map stale). Amendment tasks reconciled contracts in documentation (T7) and closed the plan (T8); re-audit **passed** at `19e35ca`. F-08 (automated wet-run replay) remains explicitly open.

---

## 2. What I now understand that I didn't before

### Three different "healthy" meanings in one product

Before the wet run, "LLM optional" vs "LLM required" was documentation noise. After deliberately breaking the LLM and re-running ingest, status, and `/ready`, the distinction is operational:

| Surface | Neo4j + Chroma | LLM | Typical operator mistake |
|---------|----------------|-----|---------------------------|
| `aria status` | Required for exit 0 | Can fail; still exit 0 | "Green status → I can ingest" |
| `aria ingest` preflight | Required | **Required** | Same |
| `GET /ready` | Reflected in JSON | Can be `false` while HTTP **200** | "API ready → ingest will work" |

The product is **intentionally asymmetric**: readiness for serving traffic is not the same as readiness for the expensive ingest pipeline. Any future UX or docs should name these three gates explicitly, not collapse them into one "health check."

### Placeholder mode is a second runtime, not a test detail

`ARIA_PLACEHOLDER_API=true` (default for integration tests) and `false` (golden path) are different programs in practice. Leaving `false` in the shell after the live session caused **two integration test failures** on `X-ARIA-Mode` assertions. That is not flakiness—it is env leakage between "prove the real stack" and "run fast mocked tests." Rule of thumb: after a live session, reset env explicitly before pytest, or wrap live steps in a subshell/profile.

### "Ingest succeeded" is not one thing

`scripts/seed_corpus.py` can look like ingest without running full wiring (entity extraction, graph write, vector index). The golden path **must** use `aria ingest` on the committed fixture. Otherwise query and impact appear to work structurally but are ungrounded—a silent false success. I would now grep any ingest shortcut for `build_full_ingest_wiring` (or equivalent) before trusting it in an e2e narrative.

### Integration markers change CI semantics, not just collection

Applying `@pytest.mark.integration` to tests that **do not** need live infra fixes the Phase 1 command (`pytest tests/integration -m integration` → 25 tests) but also means `pytest -m "not integration"` **stops running those tests** in dry CI. That tradeoff was flagged in the plan and changelog; it is easy to approve in planning and forget in pipeline design. Marker names are coupling surfaces.

### Contract-first planning vs executor helpfulness

The plan said "no new test files created by T1–T5." Executors added `test_serve.py`, `test_ingest_command.py`, and `test_status.py` anyway—good engineering, **contract violation** until T7's §2 Amendment. The audit's cold-read-before-narrative pass caught this; changelog initially mentioned only T4's tests (mild narrative-concealment for T3/T5). Lesson: either forbid tests in the contract and mean it, or write "executors may add focused unit tests; list paths in packet §Files to touch." Ambiguous prohibition invites drift toward helpfulness.

### Infrastructure health ≠ application health

Chroma reported **unhealthy** in `docker compose ps` while `GET /api/v2/heartbeat` returned 200. The stack was usable; the healthcheck was wrong (likely curl/v1 vs v2). I would not block a golden path on compose status alone without hitting the same URL the app uses.

### Live LLM on a dev machine is an environment puzzle, not a code puzzle

`.env.example` pointed at `ollama/llama3.2`, which was not installed; other Ollama models cold-started past the **12s** `probe_llm_reachable` budget. Switching to OpenAI `gpt-4o-mini` was the right session unblock—not a product bug. Wet-run plans should list "verify probe succeeds" as a **pre-flight checklist item** with acceptable fallbacks, or first-time operators burn an hour on timeouts.

### Impact "exit 0" can still mean "no graph story yet"

`aria impact reg-gdpr` returned **0 requirements** after a successful ingest: no `AFFECTS` / `ADDRESSED_BY` edges from the sample-only path. Sign-off Y was still correct for Phase 1 (CLI and preflight behavior), but "impact works" in a product sense needs seeded internal systems or richer ingest—not something to infer from exit code alone.

### Plan closure is a deliverable, not a consequence of sign-off

T6 filled the wet run log and decision log; the plan stayed **Active** with empty §8 until T8. The first audit failed partly on **process**, not runtime. "Done" in my head ≠ **Complete** in the orchestrator artifact chain.

---

## 3. Decisions I made and would make again

**Parallel T1–T5 before the live session.** Port collision, missing fixture, marker mismatch, and operator confusion are cheap to fix in isolation; fixing them mid-wet-run blurs failure attribution.

**Refuse placeholder API for the golden path.** Using `ARIA_PLACEHOLDER_API=true` would have "passed" without proving Neo4j/Chroma/LLM integration—the whole point of Phase 1.

**Use cloud LLM when local Ollama does not meet the probe budget.** Document the choice in the decision log; do not pretend the default `.env.example` path worked.

**Amend contracts instead of reverting unit tests (T7).** Eleven passing unit tests plus frozen stdout literals in §2 Amendment are better long-term signal than honoring a stale "no test files" line.

**Sign off Y with explicit caveats** (Chroma healthcheck, empty impact chain, env leakage hazard) rather than extending scope into infra or graph seeding during the same session.

**Generalizable principle:** When audit verdict is **fail** but adversarial scenarios **pass**, separate **product truth** (runtime evidence) from **process truth** (contracts, artifact chain, map staleness)—fix process without throwing away good code.

---

## 4. Decisions I made that I would change

**Plan §2 Tests row:** I would have written upfront: "T3–T5 may add `tests/unit/test_{serve,ingest_command,status}.py`" or required tests in packets. That avoids a fail audit and amendment cycle for beneficial work.

**CHANGELOG at T3/T5 commit time:** Name all three test files when added, not only T4 in a later narrative. Reduces audit F-03 / narrative-concealment noise.

**Pre-session LLM checklist:** Before starting T6, run `probe_llm_reachable` (or `aria status` with target model) once, aligned with `.env.example` or documented cloud fallback—instead of discovering timeout during ingest.

**Pytest after live steps:** Run integration tests in a clean env block (`ARIA_PLACEHOLDER_API=true` explicit) the first time, not after debugging two failures.

**Context map refresh timing:** Post-execution staleness note landed in T8; doing a lightweight "map delta" at end of T6 would have shortened the window where scout predictions looked authoritative.

**Underlying errors:** Mixed **spec precision** (absolute prohibition on tests) with **executor autonomy**; **time pressure** to finish the session before tightening docs; **optimistic sign-off** on impact without deciding whether "0 requirements" belongs in Phase 1 success criteria.

**Better rule next time:** For any shared contract sentence that starts with "No …", add the exception path in the same bullet (what *is* allowed, who owns it, which paths).

---

## 5. Patterns in my own thinking

**Trusted the plan's "no test files" as self-enforcing.** Executors (and I via review) treated it as guidance; the audit treated it as law. I should have either enforced at review time or amended before audit.

**Treated audit fail as "the golden path failed."** It did not—the wet run evidence held. I felt more doubt about the session than the evidence justified. Process findings deserved a calm documentation pass (T7/T8), not re-running the whole stack.

**Under-planned environment, over-planned code paths.** The orchestrator plan was strong on file touch lists and kill criteria for Neo4j/Cypher; weak on "your laptop's Ollama tags vs 12s timeout." Environment is where the highest re-plan risk (§5.3) actually materialized.

**Accepted sign-off Y while knowing impact was hollow.** That was correct for Phase 1 scope, but I should have written one sentence in the pickup doc: "Phase 2 must define impact success criteria" so future-me does not read Y as "impact feature validated."

**Sunk-cost signal (weak):** After a long live session, tempting to skip §8 closure "because we know it's done." T8 was cheap relative to re-audit confusion.

---

## 6. Open questions

- What is the minimal **automated** check for preflight vs `/ready` (F-08) without a full dockerized CI golden path—CliRunner with mocked deps, or a tagged manual job only?
- Should **impact** require seeded `InternalSystem` / relationship edges for MVP sign-off, or stay "CLI returns structured empty" until a data task?
- How should **CI** run `tests/integration/` after T2—always with `-m integration`, never with `not integration`, or split markers (`integration_live` vs `integration_mocked`)?
- Fix Chroma healthcheck in compose (curl, v2 heartbeat)—infra ownership vs app team?
- Align `.env.example` Ollama tags with documented warm-up / timeout, or default Phase 1 docs to cloud for first success?

---

## 7. Single paragraph synthesis

The golden wet run taught me that Aria's Phase 1 success is really about **aligning three different health semantics and two API modes** (live vs placeholder), not about getting every command to print something reassuring: ingest, status, and `/ready` answer different questions, and conflating them will waste the next operator's afternoon. The orchestrator stack worked when I treated **runtime evidence** (wet run log, preflight matrix) as ground truth and **contract/amendment/§8 closure** as a separate, non-optional finish line—executors will add good tests and slightly better copy than the plan quoted, and the right response is amend the contract, not revert or pretend the audit is petty. The surprises were environmental (Ollama tags, Chroma healthcheck, pytest env leakage) and graph-shaped (impact with zero requirements), which means the next phase should name environment preflight and data completeness as first-class success criteria, not bury them as caveats under a Y.
