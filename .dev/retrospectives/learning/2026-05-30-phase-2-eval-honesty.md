# Learning retrospective — Phase 2 eval honesty

**Date:** 2026-05-30  
**Task:** `phase-2-eval-honesty` — make the golden-set eval layer honest enough to trust in CI: fix five failing medium-tier retrieval cases, remove a always-pass sub-check stub, rename a misleading CI step, add one slow-tier replay case, then close audit findings (CI wiring, contract reconciliation, plan §8 at `HEAD`).  
**Produced:** Seven executor commits on the golden-set path (`aed77d1` T1 synthetic context · `ee55260` T3 CI label · `787d413` T2 stub + unit tests · `3a60717` T4 replay case · `678aaea` T5 CI unit gate · `63d65a2` T6 plan amendment · `e3036a3` T7 closure), decision log `.dev/decision-logs/T2-requires-multi-hop.md`, audit rev. 1 **fail** → rev. 2 **pass-with-conditions**, plan v1.2 with §8 handoff. Verification at closure: 5 unit + 33 slow goldens passed.

**Why this qualified:** One **architectural** subtask (stub removal + decision log + new test surface), a full orchestrator cycle with adversarial audit and amendment, and a deliberate product choice (Option A) that only makes sense once you understand what “eval honesty” means in this codebase versus what it does *not* mean.

---

## 1. Task context

Phase 2 was scoped in `.dev/plans/phase-2-eval-honesty/plan.md` after a pre-plan context map marked **CONDITIONAL** on seven flags (retrieval strategy A/B/C, slow-tier live vs recorded, multi-hop validation vs stub removal, CI label vs replay case, missing runner unit tests, etc.). The orchestrator resolved those up front: **Option A** (synthetic `retrieved_context` in YAML), **recorded hand-authored replay fixture** for one slow case, **remove** the `multi_hop_declared` stub, **rename** the fast-tier CI step only.

Four parallel implementation subtasks touched disjoint files. Exit criterion: `pytest tests/eval/golden_set/test_goldens.py --golden-tier=slow` green. An audit at `3a60717` **failed** on process gaps (plan §8 not at `HEAD`, runner unit tests not in PR CI, §2 test name drift, false “clean tree” claim). Three amendment subtasks wired CI, reconciled contracts in the plan/CHANGELOG, and committed closure artifacts; re-audit **passed-with-conditions** at `e3036a3` with minor SHA pointer drift (F-11).

---

## 2. What I now understand that I didn't before

### “Eval honesty” here is lens integrity, not retrieval fidelity

The phase name sounds like “make retrieval good.” The plan’s actual contract is narrower: stop **lying in the test harness**—empty context that can never pass, sub-checks that always pass, CI labels that claim replay runs when they do not, replay code that never executes. **Option A** fills `retrieved_context` with neutral template text so `run_retrieval_check`’s keyword matcher succeeds **without calling HybridRetriever**. That is honest about *what the lens measures* (substring presence against `DEFAULT_COMPONENT_KEYWORDS`) and dishonest about *whether the product retrieved anything*. The audit’s F-09 observation is the right framing: improved CI signal honesty, not retrieval quality. I should never read a green `--golden-tier=medium` as “RAG works.”

### Tier caps hide failures in PR

`--golden-tier=fast` skips medium retrieval cases; the five q1–q5 failures were **latent in PR** and **blocking in nightly** (`slow` includes `medium`). Renaming the CI step (drop “includes replay”) was label honesty only—the fast tier still does not exercise retrieval or replay. Understanding tier as a **workload filter**, not “test difficulty,” prevents surprise when PR is green but nightly was red pre-Phase 2.

### Always-pass sub-checks are worse than missing checks

`requires_multi_hop: true` on YAML cases documented intent, but `runner.py` set `sub["multi_hop_declared"] = True` whenever the flag was set—a sub-check that could never fail. Removing it (retrieval stub removal subtask) while **keeping the schema field** as documentation-only is the right split: metadata without fake signal. After removal, medium goldens still pass on keywords alone; **reintroducing the stub would not fail medium/slow goldens**—only `test_runner_unit.py` asserts `multi_hop_declared` is absent. That regression surface is why wiring unit tests into PR CI (audit F-03) was a **major**, not nitpick.

### Two different “replay tested” stories

The replay unit test uses an **inline** `ReplayFixture` with `unittest.mock.patch` on `load_replay_fixture`; the slow golden loads **`eval-replay-gdpr-erasure.json` on disk**. Golden slow tier is the real E2E for fixture shape; the unit test is fast feedback on `run_replay_check` logic. Deferred F-05 (no unit test that loads the committed JSON without mock) is a real gap if someone breaks JSON keys but keeps the mock test green. I now treat “round-trip” in plan §2 as **two artifacts**, not one test.

### Keyword tables are a hidden coupling surface

`DEFAULT_COMPONENT_KEYWORDS` in `runner.py` is duplicated inline in `graphrag_vs_vector_rag.py`. Option A must satisfy the runner table only; editing the shared dict during retrieval YAML work would silently diverge graphrag evals. Scout Surface 1 was load-bearing; the adversarial pass was right to forbid dict edits in the retrieval-YAML subtask.

### Hand-authored replay fixtures are integration puzzles

The highest re-plan risk in the plan was the slow-tier replay case: `run_replay_check` checks strategy, source count, trace keys, and nested quality `must_mention` against the fixture `response` dict. One wrong key or too few `sources` entries fails the whole slow tier. This is the same class of work as wiring E2E fixtures, not “add a YAML row.”

### Plan §2 literal test names are contracts until amended

Original §2 named `test_run_replay_check_with_fixture`; shipped code uses `test_run_replay_check_passes_with_inline_fixture`. Minor on its own, but it is **contract drift** that auditors flag (F-04). The amendment pattern—**Landed:** rows in §2 Amendment without renaming working tests—is the same lesson as Phase 1 wet run: reconcile documentation to `HEAD`, not the other way around, unless the code is actually wrong.

### Closure SHA ≠ “we ran pytest once”

First audit: plan v1.1 + §8 on disk, v1.0 at `HEAD`, dirty tree. Same failure mode as Phase 1 (T8): **sign-off in chat ≠ artifact chain at `HEAD`**. Amendment closure added CI line for `test_runner_unit.py`, committed audit, refreshed context map *Post-execution*—then re-audit found §8.1 citing `26b05116` while tip was `e3036a3` (F-11). Closure pointers are part of the deliverable.

---

## 3. Decisions I would make again

**Resolve CONDITIONAL flags in §0 before packets.** Strategy A, recorded fixture, stub removal, and rename-only CI were decided once; executors did not re-litigate Option B/C mid-flight.

**Parallel subtasks with disjoint file touch sets (T1–T4).** Retrieval YAMLs, runner + unit tests, CI label, and replay fixture/manifest do not overlap—safe parallelism and fast wall time.

**Remove stub, keep `requires_multi_hop` on schema/YAML.** Documents future validation without shipping fake passes; decision log captures rejected “implement hops now.”

**Option A over Option B/C for medium retrieval.** EvalRecorder unwired, no recording script, HybridRetriever not in golden runner—Option A was the honest *minimum* fix for “empty context always fails,” not a substitute for live retrieval later.

**Amendment after audit fail instead of reverting T2 tests or skipping CI.** T5’s second pytest line in the golden step is cheap and closes the only way stub regression could slip through PR.

**Defer F-05/F-06 (committed JSON unit load, golden negative for wrong context).** CHANGELOG explicitly records gaps; chasing them in Phase 2 would expand honesty scope into retrieval QA.

**Generalizable principle:** For eval systems, ask two questions separately—(1) does the **harness** report what it actually checked? (2) does the **system under test** participate? Phase 2 only guaranteed (1).

---

## 4. Decisions I would change

**Bind “unit tests for runner” to “unit tests in CI” in the same subtask or §2 row.** T2 added `test_runner_unit.py` and kill criteria implied regression protection, but nothing ran it in workflows until audit F-03. I would write: “PR CI golden step MUST include `pytest …/test_runner_unit.py`” in the architectural subtask or a fifth parallel “CI” touch—same lesson as Phase 1’s tests-without-CI pattern.

**Commit plan §8 in the same commit series as T4 code, not after audit.** Would have avoided F-01/F-07 and a full amendment track for documentation-only closure.

**Name the replay unit test to match §2 from the first commit, or use neutral names in contracts.** Small rename cost upfront beats F-04 reconciliation.

**Add one golden-negative for Option A in T1 scope or explicit “Phase 2.5”.** CHANGELOG defers “wrong `retrieved_context` still passes keyword check” testing; without it, Option A can rot into nonsense prose that still matches keywords—honest lens, useless signal.

**Align closure SHA in §8.1 with final T7 commit immediately.** F-11 was avoidable noise; if two T7 commits land, update the pointer on the tip commit.

**Underlying errors:** Treated “tests exist” as equivalent to “CI gated”; treated executor completion as plan closure; under-weighted **process artifacts** relative to pytest green.

**Better rule:** Any new test file called out in §2 Tests gets a matching **workflow line** in the same PR, or §2 says explicitly “local-only until Phase X.”

---

## 5. Patterns in my own thinking

**Confused “eval honesty” with “better RAG.”** The MVP pickup language (G1 retrieval failures) nudges toward fixing retrieval; the plan’s non-goals and Option A are explicit if you read §1—easy to skim past when the pain is five red tests.

**Trusted green medium tier emotionally.** After T1, five cases pass; feels like progress. Cold read: still no pipeline—only filled strings. I should label Option A mentally as **“unblock tier semantics”**, not **“fix G1.”**

**Repeated Phase 1’s “done but plan not Complete at HEAD” pattern.** Suggests a habit: run pytest, move on, defer §8 commit. The audit is doing useful nagging; the fix is procedural (closure commit checklist), not more adversarial tests.

**Underestimated CI as part of the test design.** F-03 was obvious in hindsight—grep `ci.yml` for `test_runner_unit` before calling T2 done. I looked at runner logic, not workflow invocation.

**Comfortable deferring doc drift (MVP_PICKUP, AUDIT_DIGEST).** F-08 open to Phase 5 is fine, but I may forget that pickup still describes pre-stub behavior—future me may re-debug solved problems.

---

## 6. Open questions

- When does Option A get replaced—Option B fixtures per question, or live HybridRetriever in golden runner—and what **exit criterion** marks “retrieval lens uses real retrieval”?
- Should `requires_multi_hop` gain validation tied to trace fields on replay fixtures before retrieval YAMLs, or stay doc-only until graph/hop metadata exists on `input`?
- Is one slow replay case enough for nightly confidence, or should PR fast tier run a **minimal** replay smoke (audit considered it; plan chose rename-only for fast)?
- How to test workflow YAML without brittle string asserts—dedicated workflow lint, or contract test that parses `ci.yml` pytest invocations?
- Should `graphrag_vs_vector_rag.py` and `DEFAULT_COMPONENT_KEYWORDS` be **single-sourced** to prevent the next Option A-style drift?

---

## 7. Single paragraph synthesis

Phase 2 taught me that **eval honesty is a property of the harness and CI story**, not of the retrieval stack: green medium-tier goldens after synthetic `retrieved_context` mean “keyword lens is consistent,” not “Aria retrieved the right regulation chunks,” and the dangerous bug was subtler—a sub-check that always passed and unit tests that existed but did not run on PR. The orchestrator pattern (pre-plan flags → parallel disjoint executors → cold-read audit → amendment for F-01/F-03) worked again; my recurring mistake is stopping at pytest green and treating plan §8, workflow lines, and §2 symbol names as paperwork instead of part of the same definition of done. The compounding takeaway: whenever I add or fix an eval lens, I ask **what failure mode would still look green**, then put the cheapest test **and** the CI line that would catch it in the same breath—not in a follow-up audit.
