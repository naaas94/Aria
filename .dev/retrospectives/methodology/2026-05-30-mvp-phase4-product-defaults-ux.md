# Methodology retrospective — mvp-phase4-product-defaults-ux

## 1. Task identifier

**Task:** mvp-phase4-product-defaults-ux (MVP Phase 4 — G8 placeholder default flip, README live-mode Quickstart, wet-run LLM template fields, `aria query --json` CLI smoke)  
**Date:** Context map / plan authorship 2026-05-30 · execution + audit + closure same day  
**Plan versions:** v1.0 → v1.1 (T1-amend / §0 correction) → v1.2 (T3-amend, T5-amend, §8 Complete)  
**Skills:** pre-plan-exploration v0.2 (`ee87002`), orchestrator-planning, executor-subtask-execution, auditor-review  
**One line:** Flip `ARIA_PLACEHOLDER_API` default to live mode, document operator paths, add CLI JSON contract test; two executor HALTs and one failed initial audit remediated before `f5498ab` closure.

---

## 2. Plan vs reality

### DAG vs execution

- **Planned:** `{T1, T3}` parallel → `T2` and `T4` after T1; amendment nodes T1-amend (in-place), T3-amend, T5-amend after audit.
- **Actual commit order:** `b3725f4` T1 (+ fixture in same commit) → `7e7a384` plan v1.1 (user manual) → `e06417b` T4 → `08c12ab` T2 → audit **fail** at `08c12ab` → `37b181f` T3-amend → `e86c607` T5-amend → re-audit **pass-with-conditions** at `e86c607` → `f5498ab` closure batch (plan §8, amend packets, audit rev 2).
- **Sequencing deltas:** T4 landed before T2 (both only depend on T1 — safe). **T3 never ran on the parallel path** — original packet HALTed (filled T6 session); remediated only post–audit via T3-amend. Not unsafe parallelization, but the DAG’s “T3 ∥ T1” edge hid an **inter-plan** race with Phase 1 that §3 noted softly and §5.2 #5 predicted.
- **Unsafe parallelization:** None in git (serial executor). **Latent:** Phase 1 wet-run fill before T3 template work — confirmed coupling, not caught by a hard DAG edge.

### Contracts at implementation surface

| §2 surface | Enforced in code + test? | Notes |
|------------|-------------------------|-------|
| `placeholder_api_enabled()` default `"false"` | Yes (code); partial (tests) | `api/config.py:10`; no unset-env unit test — **deferred** in §2 / decision log / F-05 |
| ASGI `client` fixture `ARIA_PLACEHOLDER_API=true` | Yes | `test_metrics.py:506-507`; suite green (123 passed at closure) |
| `_success_payload` five keys + `aria_mode` | Yes | `test_query_json_placeholder_returns_valid_payload` with explicit `env=` |
| CLI `aria query` / `--json` literals | Yes | Test invokes frozen argv shape |
| Wet-run `LLM_MODEL=` / `LLM_BASE_URL=` template lines | Yes (docs) | `.dev/MVP_PICKUP.md` template subsection; **no pytest** — grep/diff only (T3-amend) |
| Decision log path | Yes | `.dev/decision-logs/T1-g8-placeholder-default.md` in HEAD from T1 |

No hollow §2 row where tests green-masked a dropped contract: T4 forces placeholder via `CliRunner` env; metrics fixture forces placeholder before ASGI import. Deferred unset-default test is explicitly acknowledged, not silent.

### §2 / narrative vs later subtasks

- **v1.0 plan prose** (“unit tests do not read this env var”) **stale after T1 HALT** — repaired in §0 correction v1.1; decision log **Assumptions** aligned (fixture HALT documented). Drift repaired in same session, not left to audit alone.
- **Plan status “Active — T1 halted”** while `e06417b` / `08c12ab` landed — **narrative lag** (F-04) until orchestrator §8 + `f5498ab`. T1 decision log content stayed accurate; plan metadata did not.
- **CHANGELOG:** T4 bullet added at `e06417b`, **dropped** at `08c12ab` T2 — execution narrative regressed (F-03); restored by T5-amend. Tiered changelog did not prevent doc-only regression across subtasks.
- **T3 packet `ollama/llama3.2` binding** retired in v1.2 sweep — superseded by `.env.example` `gpt-4o-mini` path; no stale executor binding at amend time.

### Log tiers

| Subtask | Tier | Calibration |
|---------|------|-------------|
| T1 | architectural | **Correct** — product default + new decision-log directory + multi-file blast radius |
| T2, T3, T4 | standard | **OK** for README / template / single test file |
| T3-amend, T5-amend | standard (audit-driven) | **OK** — docs/checkbox/CHANGELOG repair; could have been one “closure hygiene” node but split matched findings |

T3 original **standard** tier was appropriate; failure was sequencing, not under-tiering.

### Closure vs committed reality

- **Implementation SHA (code/docs subtasks):** `e86c607` — plan §8.1 cites this; T1–T5-amend artifacts present at this SHA.
- **Closure SHA for plan/audit/packets:** `f5498ab` (`mvp phase 4 completed`) — bundles plan v1.2 Complete, §8, `T3-amend.md`, `T5-amend.md`, audit rev 1+2. **Re-audit R-01** caught “Complete on disk, Active in `git show HEAD:plan.md`” at `e86c607`; **repaired** in `f5498ab` before Phase 5 work (`29145df` tip).
- **First audit** ran at `08c12ab` on committed tree — correct discipline; working tree was not falsely green for closure.
- **Context map** scout `ee87002` stale vs all implementation SHAs — P-01; plan §8.4 `treat-as-prediction`; not refreshed in phase 4 (acceptable deferral).
- **MVP_PICKUP / CHANGELOG / §8** at `e86c607` matched remediation intent; **HEAD** today (`29145df`) still contains phase-4 section under `## product-defaults-ux — 2026-05-30` with all amend bullets.

---

## 3. HALTs and amendment cycles

### Executor HALTs

**Count: 2** formal HALTs (T1 KC(1), T3 KC(2)); both documented in plan §7 and packets.

| HALT | Subtask | Reason | Correct? | Resolution |
|------|---------|--------|----------|------------|
| KC(1) — `test_placeholder_query_does_not_increment` | T1 | ASGI `client` fixture read flipped default | **Yes** — real §5.4 #5 coupling; v1.0 “no env in unit tests” was wrong | Scope amend (fixture in `test_metrics.py`); landed in `b3725f4` with flip; plan v1.1 via `7e7a384` |
| KC(2) — wet run section filled (T6 session) | T3 | Template block occupied by Phase 1 golden-path log | **Yes** — §5.2 #5 falsified; not executor over-halt | T3-amend append-only path `37b181f`; original `T3.md` superseded |

**Not HALTs:** User `7e7a384` manual commit for plan/packet v1.1 — appropriate when executor should not own orchestrator amendments.

**HALT-shaped improvisation:** None observed. T2/T4 proceeded after T1 without re-opening flip; no kill criteria satisfied by checkbox edits while template missing — **audit** caught that gap (F-01/F-02), not executor self-sign-off.

### Amendment cycles

**Count: 3** amendment shapes — T1-amend (in-place scope, not a new DAG node), T3-amend (HALT), T5-amend (audit).

- **Initial audit:** `fail` at `08c12ab` — F-01 T3 missing, F-03 CHANGELOG regression, F-04 §8 empty, F-06 checkboxes stale.
- **Remediation scope:** T3-amend + T5-amend matched findings; did not expand architecture beyond append-only template and narrative repair.
- **Re-audit:** `pass-with-conditions` at `e86c607`; condition R-01 (artifacts not in HEAD) closed by `f5498ab` — **two audit passes**, one closure commit — not multiple amend waves.
- **Architectural-tier task with amendments:** First pass was **not** clean on phase intent (T3 absent, process closure lag); **code §2 contracts** were largely OK even at first audit (F-09). Audit signal was strong enough to catch doc/process drift a sharper code-only pass might have underweighted.

---

## 4. Adversarial pass calibration

### Rejected alternatives that mattered later

- **Merge T1 + T2:** Rejected — would have bloated architectural packet; T2 after T1 flip was correct, though T2’s CHANGELOG edit should have been isolated or merged with awareness of T4 entry (F-03).
- **Defer T4 `--json` smoke:** Rejected — correct; T4 was the only post-flip unit path for JSON CLI without backends.

### Load-bearing assumptions

| Assumption | Held? |
|------------|-------|
| Unit tests pass after flip + fixture only in `test_metrics.py` | **Partially falsified at HALT; closed** in T1 commit |
| CliRunner `env=` propagates for `placeholder_api_enabled()` | Yes — T4 green |
| `.dev/decision-logs/` creatable | Yes |
| Qwen model resolvable before T3 | **Bypassed** — T3-amend used `.env.example` + Ollama comment, not QUICK_TODOS scratch string |
| T3 before Phase 1 fills wet-run section | **No** — Phase 1 T6 filled first; drove T3 HALT |

### Highest re-plan risk (§5.3: T1)

- **Predicted:** G8 flip + ASGI/test coupling.
- **Actual:** HALT on metrics fixture — exactly as §5.4 #5 and §5.3 foresaw; **no full re-plan**; v1.1 scope amend sufficient.
- **Trouble elsewhere:** (1) **T3 vs Phase 1 sequencing** — equally load-bearing, resolved by amend not re-plan; (2) **T2 CHANGELOG edit** — not in §5.3; process/narrative regression (F-03); (3) **orchestrator closure lag** — T2/T4 landed before §8 (F-04).

---

## 5. Methodology gaps surfaced

### Orchestrator should have prompted for…

- **Hard inter-plan edge or kill:** If Phase 1 may fill `## Wet run log` before Phase 4 T3, block `{T1,T3}` parallel start or mandate T3-amend path in v1.0 — soft §3 note was insufficient; §5.2 #5 was predicted but not gated.
- **CHANGELOG merge discipline:** When T2 runs after T4, require “read existing phase section; do not remove prior subtask bullets” in T2 packet kill criteria — would have prevented F-03 without waiting for audit.
- **Closure batch before first audit:** Phase 3 precedent (populate §8 at Complete) — here T2/T4 committed while plan still said “T1 halted”; first audit correctly failed F-04. Template: “no doc-only subtask commits phase checklist/CHANGELOG until §8 draft or explicit orchestrator pass.”
- **Pre-plan grep for `TestClient` / `api.main` in `tests/unit`** — would have avoided v1.0 false assumption in §0 before T1 HALT.

### Executor should have blocked or escalated…

- **T2 CHANGELOG edit dropping T4 line** — not a HALT today; executor could treat “phase section loses a bullet” as KC if CHANGELOG is in files-to-touch. At minimum, `git diff CHANGELOG.md` before commit against prior phase bullets.

### Contracts schema missing or vestigial

- **§2 row for docs-only deliverables** (wet-run template) — no test column; auditors rely on grep — fine if orchestrator names verification command in packet DoD (T3-amend did).
- **“Implementation SHA vs closure SHA vs audit HEAD”** — phase 4 exhibited all three (`08c12ab` audit, `e86c607` impl, `f5498ab` artifacts); §8.1 note helped; worth standardizing in orchestrator template after phase-2/3/4 repetition.

*Do not edit skills from this file.*

---

## 6. Single sentence verdict

**Partially:** Contracts and HALT discipline held (real stops, scope-amend not silent fixes), but methodology leaked on inter-plan sequencing (T3 vs Phase 1), orchestrator closure lag behind T2/T4 commits, and CHANGELOG regression across doc subtasks — caught by a necessary `fail` → amend → `pass-with-conditions` → `f5498ab` closure cycle, not by first-pass self-consistency.
