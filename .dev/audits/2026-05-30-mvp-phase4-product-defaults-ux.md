# Audit — mvp-phase4-product-defaults-ux

**Audit document revision:** 1 (initial)  
**Date:** 2026-05-30  
**Auditor focus areas:** Integration seams (ASGI `TestClient` ↔ `placeholder_api_enabled` ↔ CLI `CliRunner` env); failure paths (unset `ARIA_PLACEHOLDER_API` post-flip). Rationale: G8 flip is the architectural risk; T1-amend and T4 exist specifically to isolate placeholder at seams.

---

## 1. Audit metadata

| Field | Value |
|-------|--------|
| Task name | mvp-phase4-product-defaults-ux |
| Plan version | 1.1 (`Active — T1 halted at kill (1); scope amended`) |
| Implementation HEAD | `08c12ab3b4bea93ff89c19cdc83b4e3af2f3f6a9` |
| Branch | `dev` (ahead of `origin/dev` by 2 commits: `e06417b` T4, `08c12ab` T2) |
| Context map | `.dev/plans/mvp-phase4-product-defaults-ux/context-map.md` — readiness **CONDITIONAL** |
| Provenance (scout SHA) | `ee87002297a495389b9bc79a510966dd30ab23f7` — **diverged** from audit HEAD |
| Scout working tree | dirty (`?? .dev/plans/`) at exploration time |
| User note | Manual commit `7e7a384` (`t1.1 manual commit`) pushed plan/packet v1.1 amendment; fixture fix landed in `b3725f4` T1 commit |
| Phase 0 discipline | Completed before reading CHANGELOG body, decision log, or plan §4+ prose beyond §1 task + §2 contracts |

---

## 2. Provenance log (Phase 0.5)

| Check | Result |
|-------|--------|
| Context map path | Present — `.dev/plans/mvp-phase4-product-defaults-ux/context-map.md` |
| SHA comparison | **diverged** — scout `ee87002` ≠ HEAD `08c12ab`. In-scope §File map `direct` paths changed on HEAD include at minimum: `api/config.py`, `README.md`, `.dev/MVP_PICKUP.md`, `.env.example`, `tests/unit/test_cli_entry.py`, `tests/unit/test_metrics.py`, `api/main.py`, `tests/eval/e2e/test_live_queries.py`, `.dev/architecture/aria/open-questions.md` |
| Working tree at scout | dirty (`?? .dev/plans/`) — plans directory now tracked; not a blocker for audit |
| Scout grep coverage | Patterns in §Coupling surfaces present (`ARIA_PLACEHOLDER_API`, `LLM_MODEL`, `CliRunner`, etc.) — no `scout-incomplete` |
| Plan §8 closure SHA | **Not recorded** — §8 still placeholder (“Populated when plan status advances to Complete”) |

### Plan-artifact provenance (`git show HEAD:<path>`)

| Artifact | Status |
|----------|--------|
| `.dev/plans/mvp-phase4-product-defaults-ux/plan.md` | present-in-HEAD |
| `.dev/plans/mvp-phase4-product-defaults-ux/context-map.md` | present-in-HEAD |
| `packets/T1.md` … `T4.md` | present-in-HEAD |
| `.dev/decision-logs/T1-g8-placeholder-default.md` | present-in-HEAD |
| Plan §8 auditor handoff | **absent-from-disk** (not populated) |

No `artifact-not-in-HEAD` or `artifact-missing` for declared binding artifacts that exist on disk.

### Provenance findings filed here

| ID | Severity | Type | Summary |
|----|----------|------|---------|
| P-01 | major | context-map-stale | Scout SHA `ee87002` ≠ HEAD `08c12ab` on all touched direct-scope files; scout-flagged predictions on those paths are stale-qualified below |

---

## 3. Context chain completeness

| Artifact | Provided | Notes |
|----------|----------|-------|
| Context map | Yes | CONDITIONAL verdict; overlap HALT with Phase 1 documented |
| Orchestrator plan v1.1 | Yes | §7 T1-amend; §8 empty |
| Packets T1–T4 | Yes | T1 re-emitted post-HALT |
| Decision log T1 | Yes | Landed |
| CHANGELOG (phase section) | Yes | **Incomplete vs commits** (T4 entry dropped at HEAD) |
| Code / commits | Yes | `b3725f4`, `7e7a384`, `e06417b`, `08c12ab` |
| Tests | Yes | `pytest tests/unit -q` → **123 passed** at audit time |
| Plan closure / §8 | **Missing** | Plan still **Active** |

Limits: No executor run logs beyond git history; T3 has no commit and no changelog line.

---

## 4. Cold-read log (Phase 0 — pinned)

1. **`api/config.py:10`** — default `"false"`; truthy set unchanged. Matches §2 typed surface.
2. **`tests/unit/test_metrics.py:505-507`** — `client` fixture sets `ARIA_PLACEHOLDER_API=true` before `TestClient(app)`. Matches amended §2 Tests.
3. **`tests/unit/test_cli_entry.py:24-38`** — `test_query_json_placeholder_returns_valid_payload` with `env={"ARIA_PLACEHOLDER_API": "true"}`; asserts five payload keys + `aria_mode == "placeholder"`. Matches §2 naming and T4 contract.
4. **No commit touches `.dev/QUICK_TODOS` or MVP_PICKUP wet-run template fields** — task statement item (3) appears unimplemented on HEAD.
5. **`CHANGELOG.md` phase-4 section at HEAD** — documents T1 and T2 only; **no T4 line** despite `e06417b` adding one (T2 commit regressed narrative).
6. **`.dev/MVP_PICKUP.md` Phase 4 checklist** — G8 `[x]`; README live block, QUICK_TODOS, and optional `--json` smoke still `[ ]` even though README/T4 code exist.
7. **Plan metadata** still says “T1 halted” while T2/T4 commits exist — process/narrative lag.
8. **Architecture inventory** (`public-interface-inventory.md`, `known-coupling-surfaces.md`) still states placeholder default **true** — adjacent doc drift (Phase 5 G10 explicitly deferred in T1 decision log).
9. **Historical CHANGELOG** (~line 120) still describes CLI placeholder default `true` — pre-phase narrative not reconciled (observation unless consumers treat section as current).

---

## 5. Findings table

| ID | Sev | Type | Phase | Subtask | One-line description |
|----|-----|------|-------|---------|----------------------|
| F-01 | **major** | intent-drift | 1 | T3 | Task statement item (3) not implemented: no `LLM_MODEL=` / `LLM_BASE_URL=` template fields; `.dev/QUICK_TODOS` unchanged |
| F-02 | **major** | intent-drift | 1 | — | Phase 4 incomplete: 3 of 4 task bullets undelivered or unverified in MVP_PICKUP |
| F-03 | **major** | narrative-concealment | 1 | T2 | T4 changelog entry present in `e06417b` but **absent** after `08c12ab` T2 — execution narrative regressed |
| F-04 | major | process-violation | 0.5/1 | — | Plan §8 auditor handoff empty; plan status still Active post T2/T4 |
| F-05 | minor | coverage-gap | 5 | T1 | No unit test asserts `placeholder_api_enabled()` is `False` when env unset (deferred in §2 — acknowledged) |
| F-06 | minor | intent-drift | 1 | T2/T4 | MVP_PICKUP Phase 4 checkboxes not updated for completed README / CLI smoke work |
| F-07 | minor | contract-violation | 2 | — | Architecture `public-interface-inventory.md` / `known-coupling-surfaces.md` still document default `true` (Phase 5 scope; creates operator confusion) |
| F-08 | observation | — | 1 | T1 | Manual `7e7a384` commit correctly lands plan v1.1 amendment; code fixture already in `b3725f4` |
| F-09 | observation | — | 2 | T1/T2/T4 | T1/T2/T4 code contracts otherwise align with §2 on inspected surfaces |
| P-01 | major | context-map-stale | 0.5 | — | Scout SHA stale vs HEAD (see §2) |

---

## 6. Detailed findings (above minor)

### F-01 — T3 not executed (major · intent-drift)

**Expected (§1 task statement item 3; T3 packet):** Wet run log **template** in `.dev/MVP_PICKUP.md` gains explicit `LLM_MODEL=` and `LLM_BASE_URL=` fields; `.dev/QUICK_TODOS` consolidated or cleared.

**Found:** No git commit references T3. `.dev/QUICK_TODOS` remains a single vague line (“Local model swap for qwen something”). `## Wet run log` section contains **filled Phase 1 session data** (T6) with LLM values only inline in prose (`aria status` line), not as dedicated template fields. T3’s partition constraint allowed editing template block only — executor never ran.

**Evidence:** `git log fae6b0c..HEAD --oneline --name-only` lists no T3; `grep LLM_MODEL .dev/MVP_PICKUP.md` hits session log lines only, not template placeholders.

---

### F-02 — Phase incomplete vs task statement (major · intent-drift)

**Expected:** Four concrete deliverables in §1.

**Found:**

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | G8 flip default | **Done** (`api/config.py`, decision log, MVP G8 row) |
| 2 | README live-mode block | **Done** (`README.md` § Live mode, HTTP Modes) |
| 3 | Wet run template LLM fields | **Not done** (F-01) |
| 4 | `aria query --json` smoke | **Done** (test + pytest green) |

DAG allowed T3 ∥ T1; absence of T3 still violates overall phase intent.

---

### F-03 — CHANGELOG lost T4 entry (major · narrative-concealment)

**Expected:** Tiered changelog documents each landed subtask.

**Found:** `git show e06417b:CHANGELOG.md` includes T4 bullet. `git show 08c12ab:CHANGELOG.md` (HEAD) shows only T1 + T2 under `mvp-phase4-product-defaults-ux`. T2 commit edited CHANGELOG without preserving T4 line.

**Evidence:** Diff between `e06417b` and `08c12ab` on `CHANGELOG.md`.

---

### F-04 — Plan not closed; §8 empty (major · process-violation)

**Expected:** Phase-3 precedent populates §8 on completion with verification SHA.

**Found:** `plan.md` **Status:** Active — T1 halted…; §8 = placeholder. Executors landed T2/T4 after HALT remediation but orchestrator closure not performed.

---

### P-01 — Context map stale (major · context-map-stale)

Scout commit `ee87002` predates all implementation commits. Findings tied to scout `suspect_modified` / coupling tuples on touched files are **stale-qualified**; implementation verification used HEAD code directly.

---

## 7. Adversarial test log (Phase 4)

### Focus A — Integration seams (required)

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| A1: `test_metrics.client` after flip | `/query` uses placeholder; `RETRIEVAL_COUNTER` flat in `test_placeholder_query_does_not_increment` | Fixture sets env before import; test class unchanged | **passes** |
| A2: T4 `CliRunner` + `load_dotenv()` | `env={"ARIA_PLACEHOLDER_API": "true"}` wins for `os.getenv` in `placeholder_api_enabled()` | Click patches env during invoke; test passes at HEAD | **passes** |
| A3: Scout Surface 2 — default vs `.env.example` comment | Code default `false`; example documents live default | `.env.example:50-52` aligned | **passes** |
| A4: Scout Surface 5 — T3 template vs Phase 1 fill | Template fields before session fill | Phase 1 filled log; T3 never added fields | **fails** (F-01) |

### Focus B — Failure paths (unset env post-flip)

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| B1: Unset `ARIA_PLACEHOLDER_API` | `placeholder_api_enabled()` → False; live path or connection errors | `api/config.py:10` default `"false"` | **passes** (by design) |
| B2: CLI `aria query` without env on developer machine with `.env` placeholder true | Follows `.env` | `load_dotenv()` in `aria/cli/main.py:27` — operator `.env` can override; documented in README | **unknown** (environment-dependent) |
| B3: E2E `test_live_queries` without override | Nightly sets false; local may hit live | Docstring updated; nightly workflow unchanged | **passes** (contract) |

### Focus C — Regression (CHANGELOG / docs)

| Scenario | Expected | Actual | Result |
|----------|----------|--------|--------|
| C1: Phase-4 CHANGELOG lists all landed subtasks | T1, T3, T4, T2 entries | T1, T2 only at HEAD | **fails** (F-03) |

---

## 8. Coverage gap list (Phase 5 — prioritized)

| Priority | Gap | Severity | Notes |
|----------|-----|----------|-------|
| 1 | T3 wet-run template + QUICK_TODOS | **major** | Untested operator capture path for qwen swap (Flags 3, 5) |
| 2 | `placeholder_api_enabled()` unset-env | minor | Explicitly deferred in §2; T4 only tests explicit `true` |
| 3 | `aria query --json` service_unavailable JSON | minor | Deferred in T4 changelog text (when restored) |
| 4 | README ↔ `api/config.py` spelling drift | minor | Deferred per T2 changelog |
| 5 | Architecture inventory default `true` | minor | Phase 5 G10; creates confusion until updated |

**Kill criteria:** T1 kill (1) satisfied — `pytest tests/unit -q` → 123 passed. T3 kill (1) for qwen model ID never evaluated (T3 not run).

---

## 9. Phase 1 — Intent traceability (summary)

- **Plan §1 → code:** Items 1, 2, 4 map to commits; item 3 does not (F-01, F-02).
- **Non-goals:** Respected (no impact `--json` change, no Phase 5–6 scope creep in code).
- **T1 HALT / §7 amendment:** User manual commit `7e7a384` matches plan v1.1; fixture in `b3725f4`. Plan §0 correction acknowledges metrics fixture — no `narrative-concealment` on HALT once §0 read.
- **Packet → diff:** T1, T2, T4 files match packets; T3 packet has **no diff**.
- **MVP_PICKUP checklist:** Drift vs reality (F-06).
- **Interface inventory → §2:** `placeholder_api_enabled` default updated in code; scout inventory still says `"true"` (stale-qualified / Phase 5).

---

## 10. Phase 2 — Contract compliance (summary)

| Contract surface | Status |
|------------------|--------|
| `placeholder_api_enabled()` default `"false"` | **OK** |
| `test_metrics.py` `client` fixture `monkeypatch.setenv(..., "true")` | **OK** |
| `test_query_json_placeholder_returns_valid_payload` name + five keys + `aria_mode` | **OK** |
| CLI literals `aria query`, `--json` | **OK** (unchanged paths) |
| Literal `ARIA_PLACEHOLDER_API` in README / OpenAPI / `.env.example` | **OK** |
| Decision log path `.dev/decision-logs/T1-g8-placeholder-default.md` | **OK** |

Typed-surface admission (a)(b)(c): flip admitted in `getenv` default; T4 exercises CLI path with explicit env, not unset-default false — matches deferred gap documentation.

---

## 11. Phase 3 — Decision log audit

**T1-g8-placeholder-default.md:** Chosen flip implemented; rejected alternatives not present in code; **Assumptions** correctly record metrics fixture HALT; deferred unset-env test matches §2.

**Stale prose:** Plan body still opens with “T1 halted” while T1 completed — plan-level `decision-log-stale` equivalent (F-04), not T1 log content.

No `narrative-concealment` between cold-read HALT/fixture issue and decision log — log documents amend.

---

## 12. Scout-prediction reconciliation

| Scout prediction | Type | Outcome | Finding |
|------------------|------|---------|---------|
| Surface 1 — default true footgun | confirmed coupling | **verified** — flipped to false | — |
| Surface 2 — getenv vs docs | confirmed | **verified** — aligned on HEAD | — |
| Surface 3 — LLM_MODEL duplication | confirmed | **not-tested** for T3 template | F-01 |
| Surface 4 — CliRunner needs explicit env post-flip | confirmed | **verified** — T4 + fixture | — |
| Surface 5 — MVP_PICKUP template vs Phase 1 fill | confirmed | **prediction-divergence** — Phase 1 filled before T3; T3 never ran | F-01 |
| Surface 6 — “MVP branch” | suspected | **ruled-out** — landed on `dev` per plan §0 | — |
| Flag 1 G8 flip vs doc-only | ambiguity | **verified** — flip chosen | — |
| Flag 4 `--json` smoke asserts | ambiguity | **verified** — five keys + aria_mode | — |
| Flag 3/5 qwen / LLM fields | ambiguity | **not-tested** | F-01 |
| `placeholder_api_enabled` suspect_modified | inventory | **verified** modified | stale-qualified P-01 |

---

## 13. Verdict

**`fail`**

**Must resolve before merge / phase sign-off:**

1. **F-01 / F-02** — Execute T3 (wet run template `LLM_MODEL=` / `LLM_BASE_URL=`, QUICK_TODOS consolidation) per packet, or amend plan/task statement with explicit deferral ID if intentionally dropped.
2. **F-03** — Restore T4 bullet in `CHANGELOG.md` (and avoid dropping it on future doc commits).
3. **F-04** — Orchestrator closure: update plan status, populate §8 with verification SHA (`08c12ab` + pytest count), refresh MVP_PICKUP Phase 4 checkboxes.

**Recommended (non-blocking):** F-06 checklist sync; F-07 architecture inventory when Phase 5 runs; push `dev` if `ahead 2` is unintentional.

---

## 14. Commits reviewed

| SHA | Message | Scope |
|-----|---------|-------|
| `b3725f4` | T1: Flip ARIA_PLACEHOLDER_API default to false (G8) | Code, docs, decision log, metrics fixture |
| `7e7a384` | t1.1 manual commit | Plan v1.1 + T1 packet (user) |
| `e06417b` | T4: aria query --json CLI smoke | Test + CHANGELOG (T4 line since lost) |
| `08c12ab` | T2: README live-mode Quickstart | README + CHANGELOG (T2 only at HEAD) |

**Not found:** T3 commit.

---

# Re-audit — revision 2 (remediation traceability)

**Audit document revision:** 2 · **Supersedes:** revision 1 verdict and finding **status** for remediation surfaces (F-01–F-04, F-06, P-01 reconciliation). **Does not edit** revision 1 body above — historical record only.

**Date:** 2026-05-30  
**Implementation HEAD (code/docs commits):** `e86c6072f4fa05aab8ffa8dae3a8e3442b78644e`  
**Closure artifacts:** `plan.md` v1.2 **Complete** + §8 populated on **working tree**; not yet in `git show HEAD:plan.md` (see R-01).  
**Phase 0 discipline:** Fresh cold read at `e86c607` before reading plan §7–§8 remediation narrative.

### Omission-free artifact checklist (re-pass)

| Surface | Opened |
|---------|--------|
| Revision 1 audit | Yes |
| `plan.md` (disk + `git show HEAD:`) | Yes |
| `packets/T3-amend.md`, `packets/T5-amend.md` | Yes (disk) |
| `CHANGELOG.md`, `.dev/MVP_PICKUP.md`, `.dev/QUICK_TODOS` | Yes |
| Commits `37b181f`, `e86c607` | Yes |
| `api/config.py`, `tests/unit/test_cli_entry.py`, `tests/unit/test_metrics.py` | Yes |
| `pytest tests/unit -q` | Yes → **123 passed** |

---

## R2.1 Provenance log (remediation HEAD)

| Check | Result |
|-------|--------|
| Verification SHA (§2 contracts) | `e86c607` — T5-amend; `pytest tests/unit -q` → 123 passed |
| Scout SHA vs `e86c607` | Still **diverged** (`ee87002`) — P-01 remains valid; plan §8.4 acknowledges |
| `git show HEAD:plan.md` §8 | **Empty placeholder** — closure narrative on disk only (R-01) |
| `git show HEAD:.dev/audits/2026-05-30-mvp-phase4-product-defaults-ux.md` | **absent** — this file untracked at audit time |
| `git show HEAD:packets/T3-amend.md` | **absent** — packet on disk, not committed |

---

## R2.2 Cold-read log (Phase 0 @ `e86c607`)

1. `CHANGELOG.md` phase-4 section lists T1, T2, T4, T3-amend, T5-amend — T4 bullet restored.
2. `.dev/MVP_PICKUP.md:320-329` — dedicated template block with `LLM_MODEL=` / `LLM_BASE_URL=` lines + Ollama comment.
3. `.dev/QUICK_TODOS` — pointer to MVP_PICKUP template; vague qwen line gone.
4. Phase 4 checklist lines 199–202 — all `[x]`.
5. `api/config.py:10` default `"false"`; metrics `client` fixture still sets `ARIA_PLACEHOLDER_API=true`.
6. `test_query_json_placeholder_returns_valid_payload` unchanged and present.
7. T6 session block (lines 251–316) **immutable**; header retitled to reference template below — matches T3-amend append-only contract.
8. `plan.md` on disk: **Complete**, §8 filled with remediation cross-links; **HEAD plan** still v1.1 Active — process gap until commit.

---

## R2.3 Finding status vs revision 1

| Prior ID | Prior sev | Prior type | Status | Evidence @ `e86c607` + disk |
|----------|-------------|------------|--------|------------------------------|
| F-01 | major | intent-drift | **resolved** | `37b181f` — `## Wet run log template` with `LLM_MODEL=` / `LLM_BASE_URL=`; QUICK_TODOS consolidated |
| F-02 | major | intent-drift | **resolved** | All four §1 deliverables landed (T3 via amend path documented in plan §7) |
| F-03 | major | narrative-concealment | **resolved** | `e86c607` — T4 bullet in `CHANGELOG.md` lines 11–12 |
| F-04 | major | process-violation | **resolved** (disk) / **open** (HEAD) | §8 Complete on working tree; `git show HEAD:plan.md` still Active + empty §8 — commit closure batch (R-01) |
| F-05 | minor | coverage-gap | **open** | Still no unset-env test for `placeholder_api_enabled()`; explicitly deferred in §2 |
| F-06 | minor | intent-drift | **resolved** | `e86c607` — Phase 4 rows 199–202 `[x]` |
| F-07 | minor | contract-violation | **open** | `public-interface-inventory.md` / `known-coupling-surfaces.md` still say default `true` (Phase 5 G10) |
| F-08 | observation | — | **superseded** | Manual `7e7a384` + T1-amend narrative now closed in plan §8 |
| F-09 | observation | — | **resolved** | Re-verified: §2 surfaces hold at `e86c607` |
| P-01 | major | context-map-stale | **open** | Scout SHA unchanged; acceptable per plan §8.4; refresh is orchestrator follow-up |

---

## R2.4 New findings (revision 2 only)

| ID | Sev | Type | Description |
|----|-----|------|-------------|
| R-01 | major | artifact-not-in-HEAD | Plan v1.2 **Complete** + §8.1–§8.6, `packets/T3-amend.md`, `packets/T5-amend.md`, and this audit file exist on disk but are **not** in `e86c607`. Plan §8.1 documents this; auditors at `git show HEAD:` only see pre-closure plan. **Action:** single closure commit bundling plan, amend packets, audit rev 1+2. |
| R-02 | observation | — | Immutable T6 session prose (line ~301) says `ARIA_PLACEHOLDER_API=true (default for mocked TestClient suite)` — pre-flip wording frozen in session log; template below is correct. No remediation required. |

---

## R2.5 Adversarial re-check (integration seams)

| Scenario | Result |
|----------|--------|
| A1 metrics fixture + flip | **passes** (unchanged) |
| A2 T4 CliRunner env isolation | **passes** |
| A4 T3 template vs session | **passes** — append-only; Surface 5 closed via new template section |
| C1 CHANGELOG lists all subtasks | **passes** at `e86c607` |

---

## R2.6 Scout-prediction reconciliation (remediation delta)

| Scout prediction | Rev 1 outcome | Rev 2 outcome |
|------------------|---------------|---------------|
| Surface 5 — template vs Phase 1 fill | prediction-divergence (F-01) | **verified** — T3-amend append path |
| Flag 3 / 5 — LLM fields / qwen | not-tested | **verified** — template uses `.env.example` values + Ollama comment, not `qwen something` |

---

## R2.7 Verdict (revision 2)

**`pass-with-conditions`**

**Resolved (merge-ready for phase intent):** F-01, F-02, F-03, F-06, F-09; remediation code/docs at `e86c607`; unit suite green.

**Conditions before archive-grade closure:**

1. **R-01** — Commit `plan.md` (Complete + §8), `packets/T3-amend.md`, `packets/T5-amend.md`, and `.dev/audits/2026-05-30-mvp-phase4-product-defaults-ux.md` so `git show HEAD:` matches §8.2 artifact chain.
2. **F-05 / F-07** — Accept as deferred (documented) or track under Phase 5; do not block phase-4 sign-off.
3. **P-01** — Optional context-map refresh on a later orchestrator cycle.

**Still not required:** Re-explore codebase for stale scout map (auditor reports only).

### Remediation commits reviewed (revision 2)

| SHA | Message |
|-----|---------|
| `37b181f` | T3-amend: append wet run log template and consolidate QUICK_TODOS |
| `e86c607` | T5-amend: restore T4 CHANGELOG bullet; sync Phase 4 pickup checklist |

**Branch note:** `dev` was **ahead 4** of `origin/dev` at re-audit (`b3725f4`…`e86c607`); push when ready.
