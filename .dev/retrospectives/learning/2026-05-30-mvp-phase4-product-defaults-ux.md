# Learning retrospective — MVP Phase 4 product defaults & operator UX

**Date:** 2026-05-30  
**Task:** `mvp-phase4-product-defaults-ux` — resolve **G8** (flip `ARIA_PLACEHOLDER_API` code default to `false`), add README live-mode Quickstart, add wet-run `LLM_MODEL` / `LLM_BASE_URL` template fields, add `aria query --json` CLI smoke test.  
**Produced:** Commits `b3725f4` (T1 + T1-amend fixture) → `7e7a384` (plan v1.1, manual) → `e06417b` (T4) → `08c12ab` (T2) → `37b181f` (T3-amend) → `e86c607` (T5-amend); plan v1.2 **Complete** with §8 at closure SHA `e86c607`; decision log `.dev/decision-logs/T1-g8-placeholder-default.md`; audit initial **`fail`** then **`pass-with-conditions`** (`.dev/audits/2026-05-30-mvp-phase4-product-defaults-ux.md`). Verification: **123 passed** (`pytest tests/unit -q`).

**Why this qualified:** Phase 4 had one **architectural** subtask (the G8 default flip), two executor HALTs with plan amendments, an inter-plan sequencing collision with Phase 1's golden wet run, and an audit that failed on narrative/process before code contracts broke. Smallest MVP phase on the calendar, densest ratio of process correction to lines of product code changed.

---

## 1. Task context

Pre-plan exploration at scout SHA `ee87002` returned **CONDITIONAL** readiness: G8 was an open product fork (flip vs document-only), and the wet-run log template in `MVP_PICKUP.md` overlapped Phase 1's live-session capture. The orchestrator resolved G8 as a **code default flip on `dev`**, partitioned T3 to template lines only, and marked T4 (`--json` smoke) mandatory—not optional—because post-flip placeholder mode would only be unit-testable with explicit env isolation.

Execution DAG: parallel **{T1, T3}** → sequential **T2, T4** after T1. Reality: T1 HALT on `test_metrics.py` ASGI fixture → v1.1 scope amendment; T3 never ran (Phase 1 T6 filled the template first) → T3-amend append-only path; initial audit **fail** on missing T3, CHANGELOG regression, empty plan §8 → T5-amend + orchestrator §8 closure. All four §1 deliverables landed; F-05 (unset-env unit test) and F-07 (architecture inventory still says default `true`) explicitly deferred.

---

## 2. What I now understand that I didn't before

### A code default is an operator contract, not a README footnote

G8 was open since the architecture folder was drafted. The real fork was: keep `placeholder_api_enabled()` default `"true"` and document live mode, or flip the default and document placeholder as the override. **Document-only preserves demo ergonomics but lies to anyone who never reads docs**—they get plausible synthetic compliance answers and believe the stack works. Flipping the default makes missing Neo4j/Chroma/LLM **visible** (503, preflight failures) instead of silent. That is a product decision with a single line of code as its enforcement mechanism. I should treat env defaults in operator-facing systems the same way I treat API response shapes: changing them is architectural even when the diff is one string.

### Default flips propagate through integration seams, not through "the config file"

The flip in `api/config.py:10` was the easy part. Load-bearing couplings the plan (and HALT) surfaced:

- **ASGI `TestClient` fixtures** that import `api.main:app` without env override now run live `/query` and increment retrieval metrics—`test_placeholder_query_does_not_increment` failed until the `client` fixture got `monkeypatch.setenv("ARIA_PLACEHOLDER_API", "true")`.
- **OpenAPI description** in `api/main.py` hard-coded the old default wording.
- **E2E docstrings** (`test_live_queries.py`) documented operator expectations tied to the old default.
- **Historical CHANGELOG prose** (~line 136) still describes CLI placeholder default `true` from the April CLI launch—unchanged in Phase 4, still a narrative hazard for future readers.

The v1.0 plan claim that "unit tests do not read this env var" was **wrong for exactly one file**—but that file was enough to HALT T1. The lesson: before flipping a global default, grep for `TestClient(app)`, `import api.main`, and bare `os.getenv` on that key across **all** test tiers, not just service-layer tests that pass `use_placeholder=` explicitly.

### CliRunner `env=` is the CLI test isolation primitive post-flip

T4 forces `env={"ARIA_PLACEHOLDER_API": "true"}` on `runner.invoke` so the smoke test stays backend-independent after G8. Click patches `os.environ` during invocation **before** `load_dotenv()` in `aria/cli/main.py` runs, so explicit `env=` wins. Without that, a developer's `.env` with `ARIA_PLACEHOLDER_API=true` could mask a broken test, and post-flip a test that assumed the old default would pass vacuously. **Any CLI test that depends on mode must set env explicitly**—never rely on code default or disk `.env` in unit tests.

### Shared operator docs need append-only remediation, not overwrite

T3's partition constraint (edit template block lines 249–268 only) was correct for parallel execution with T1—but Phase 1 T6 had already **filled** that block with a complete golden-path session. T3's kill criterion (2) fired: editing "the template" would destroy session history. T3-amend's **append a copy-paste template subsection** after the closed fence was the right product choice: preserve immutable session record, give future operators blank `LLM_MODEL=` / `LLM_BASE_URL=` lines. This is the same class of problem as eval golden early-exits (Phase 2) and wet-run sign-off (Phase 1)—**control flow and document lifecycle dominate** more than the content of the fields being added.

### CHANGELOG is a merge surface for parallel doc subtasks

T4 landed first and added its tiered bullet. T2's commit edited `CHANGELOG.md` and **dropped the T4 line**—audit F-03, narrative-concealment. T5-amend restored it from `git show e06417b:CHANGELOG.md`. I now read parallel executor commits that touch the same markdown file as **conflict-prone even when git merges cleanly**: semantic loss does not always produce a merge conflict. Phase 3's clean audit did not immunize Phase 4; the regression happened in a two-line T2 doc commit.

### `--json` smoke asserts a frozen payload contract, not "JSON works"

T4 asserts all five `_success_payload` keys (`answer`, `sources`, `retrieval_strategy`, `trace`, `aria_mode`) and `aria_mode == "placeholder"`. That choice resolved context-map Flag 4 without ambiguity. The deferred gap—no test for `service_unavailable` JSON when live backends missing—is intentional: T4 covers the happy placeholder path only; unset-default-false behavior is design-by-default in `api/config.py`, not exercised in unit tests (F-05 deferred).

### Inter-plan DAG notes are warnings, not enforcement

Plan §3 noted T3 should complete before Phase 1 fills the wet run log. Phase 1 ran anyway (correctly—Phase 1 was higher priority for MVP sign-off). The DAG edge was soft; the HALT was hard. **When two plans share a file region, either serialize execution or design amend paths upfront**—"noted as sequencing constraint" is not enough if the other plan can legitimately win the race.

### Audit cold-read caught code truth before narrative truth

Initial audit at `08c12ab`: T1/T2/T4 **code matched §2 contracts**; failures were T3 missing (F-01/F-02), CHANGELOG incomplete (F-03), plan still "Active — T1 halted" (F-04), MVP_PICKUP checkboxes stale (F-06). Re-audit at `e86c607` after T3-amend + T5-amend: **pass-with-conditions** with R-01 (closure artifacts on disk but not yet in HEAD at audit time). The architectural risk (G8 flip) was contained by T1-amend; the phase almost failed on **operator documentation and process closure**, not on retrieval or CLI behavior.

---

## 3. Decisions I would make again

**Flip the code default (G8), not document-only.** Aligns product intent with enforcement; nightly CI already sets `false` explicitly; decision log alternatives section documents the rejected path clearly.

**Expand T1 scope on HALT instead of spawning T1.1.** Single fixture file, single `monkeypatch.setenv`—plan §5.3 option (a). Keeps DAG unchanged and avoids packet proliferation.

**T3-amend option 2 (append template) over option 1 (close without template) or option 3 (archive/replace session).** Preserves T6 golden-path history; satisfies audit F-01/F-02 without user approval for data movement.

**Mandatory T4 post-flip.** Context map listed CLI smoke as optional; plan rejected deferral (§5.1). Correct—after default flip, explicit env isolation in tests is load-bearing; `--json` had zero coverage.

**Resolve Flag 1 + Flag 2 in plan §0 before packets.** G8 flip on `dev`, not a mythical "MVP release branch," unblocked T2/T4 kill criteria that require confirmed flip outcome.

**Tiered CHANGELOG with explicit coverage-gap deferrals.** F-05 (unset-env test), F-07 (architecture inventory), T4 `service_unavailable` path—documented as deferred, not silent omissions. Auditor treated them as accepted scope.

**Generalizable principle:** For **product-default changes**, plan the **seam inventory** (ASGI mounts, CliRunner, OpenAPI, operator docs, architecture inventory) in the same breath as the one-line default change. The default is the architectural act; the seams are where it actually hurts.

---

## 4. Decisions I would change

**v1.0 plan assumption: "unit tests do not read this env var."** Should have been verified by grep for `TestClient` + `api.main` before authoring §5.2 #1. One false assumption caused HALT and a manual plan v1.1 commit (`7e7a384`).

**Serialize T3 before Phase 1 wet run—or pre-design T3-amend in the original plan.** The Surface 5 coupling was **confirmed** in §5.4; only the amend packet was missing until HALT. For shared template regions, default packet should be append-only if another plan might fill first.

**CHANGELOG edit discipline for parallel doc executors.** T2 should have re-read full phase-4 section before commit, or T5-amend should have been anticipated in the plan as "closure hygiene" from the start (Phase 3 closure did not need this because subtasks touched disjoint doc regions).

**Commit closure batch atomically with §8 fill.** R-01 flagged plan v1.2 Complete, amend packets, and audit rev 2 on disk but not in `git show HEAD:` at re-audit. Same class of drift as Phase 1's §8-at-HEAD lesson—process truth lags working tree.

**Refresh architecture inventory in the same phase as a default flip—or strike a stronger "stale until Phase 5" warning in README.** F-07 is deferred to G10, but `public-interface-inventory.md` still saying default `true` contradicts live code for anyone reading architecture before code.

**Add the deferred unset-env unit test—or promote it from deferral sooner.** One-liner asserting `placeholder_api_enabled()` is `False` with env unset would lock the G8 contract without backends. Deferred to keep T1 small; cheap insurance worth taking at closure.

**Underlying errors:** Optimistic coupling assumptions in pre-plan grep; treating soft DAG notes as sufficient for shared files; underweighting CHANGELOG as a concurrent write surface.

**Better rule:** Before flipping any global default, run a **seam checklist** (ASGI, CliRunner, OpenAPI, `.env.example`, architecture inventory, historical CHANGELOG) as blocking plan §0 work, not adversarial §5.4 afterthought.

---

## 5. Patterns in my own thinking

**Equated "0.5 day phase" with "low seam density."** Four bullets, ~7 commits, two HALTs, one audit fail—more process correction per LOC than Phase 3 observability. Scope size ≠ integration risk.

**Trusted "service-layer tests pass `use_placeholder=`" as proxy for entire test suite.** Service tests and HTTP-mount tests are different species. I should default to searching for app import paths whenever env gates global behavior.

**Let Phase 1 and Phase 4 run in parallel on `MVP_PICKUP.md` without hard gate.** Reasonable for velocity; the HALT was predictable from §5.4 #2. I did not escalate the soft dependency to a user-visible "run T3 first or use amend path."

**Manual orchestrator commit mid-HALT (`7e7a384`).** Correct intervention to land plan v1.1 while executor waited—but signals I should have amended scope **before** first T1 execution given metrics fixture pattern existed in `tests/test_telemetry_endpoints.py` as a precedent.

**Relief that code passed audit Focus A while narrative failed.** Risky comfort: I could have shipped broken operator UX (no LLM template fields, stale checkboxes) with green unit tests. **Green pytest is necessary, not sufficient, for operator-UX phases.**

**Compared Phase 4 unfavorably to Phase 3's first-pass audit.** Phase 3 froze metric schemas upfront; Phase 4 had a false §5.2 assumption and a race on shared docs. The difference is pre-plan verification depth on couplings, not executor quality.

**Did not treat historical CHANGELOG (~April CLI launch) as in-scope narrative debt.** Phase 4 flip makes that old bullet actively misleading. Deferred because non-goals said no full doc rewrite—but I should flag "historical section contradicts current default" explicitly in pickup or AUDIT_DIGEST.

---

## 6. Open questions

- Should `.dev/decision-logs/` become standard for every architectural tier subtask, or only when product forks exist? T1 log was load-bearing for audit Phase 3; no T2–T4 logs needed.
- Is there a lightweight CHANGELOG convention for parallel subtasks (e.g. append-only bullets, never edit sibling lines) that prevents F-03 class regressions without a T5-amend track every phase?
- When scout SHA diverges from HEAD (P-01 every phase so far), is context-map refresh a **closure gate** or optional hygiene? Phase 4 plan says optional; stale map predicted Surface 5 correctly anyway.
- For operator docs shared across phases (`MVP_PICKUP.md`), is **append-only template below session** the permanent pattern, or should templates live in a separate file to avoid races entirely?
- Does a developer `.env` with `ARIA_PLACEHOLDER_API=true` after G8 flip re-create the old footgun locally—and is README live-mode block sufficient warning, or should `.env.example` uncomment a explicit `false` line?

---

## 7. Single paragraph synthesis

Phase 4 taught me that **changing a product default is an architectural act whose blast radius is measured in integration seams, not in the size of the diff**—one string in `api/config.py` HALT'd T1 on an ASGI metrics fixture the plan wrongly assumed was isolated, and it forced every CLI/HTTP test path to declare placeholder intent explicitly. The flip was the right product call; the drama was inter-plan document races (Phase 1 filled the wet-run block before Phase 4's template task ran), CHANGELOG semantic regression across parallel doc commits, and closure artifacts lagging HEAD—the same roadmap-truth failure mode as Phases 1 and 3, but here it almost failed the phase despite **123 green unit tests**. The compounding lesson: **for operator-UX work, grep `TestClient` and shared markdown regions before you plan; design append-only amend paths when two phases touch the same template; and treat CHANGELOG sections as shared mutable state that needs the same contract discipline as code.**
