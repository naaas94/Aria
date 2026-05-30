# Methodology retrospective — phase-5-doc-architecture-hygiene

## 1. Task identifier

**Task:** phase-5-doc-architecture-hygiene (MVP Phase 5 — doc & architecture hygiene: path_to_release §1 supersession, README production call graph, architecture folder approval, AUDIT_DIGEST sync after Phase 2+3)  
**Date:** Context map / planning 2026-05-25 · execution / audit / closure 2026-05-30  
**Plan versions:** v1.0 → v1.1 (§8 auditor handoff, Status Complete)  
**Skills:** pre-plan-exploration v0.2, orchestrator-planning v0.6, executor-subtask-execution, auditor-review v0.4  
**One line:** Close `MVP_PICKUP.md` §204–209 / criterion 6 (“docs match code”) with four doc-only subtasks; initial audit `fail` on closure-not-in-HEAD; closure repaired in `1e8a66d` without a recorded re-audit.

---

## 2. Plan vs reality

### DAG vs execution

- **Planned:** `{T1, T2, T3}` parallel (any order); **T4** blocked on Phase 2 + Phase 3 Complete (external gate).
- **Actual commit order:** T1 → T2 → T3 → T4 (`614fcf2` → `855abcb` → `4fe003b` → `153a51f`), then closure `1e8a66d` (plan + context-map §Post-execution), then `29145df` (same message + unrelated `changelog-dual-track-rationale.md`).
- **Sequencing:** Single serial executor session, not parallel agents; disjoint files — no merge conflicts. T4 correctly last relative to external gates; intra-plan parallel group was safe but not exploited.
- **Unsafe parallelization:** None observed.

### Contracts at implementation surface

| §2 surface | Enforced? | Notes |
|------------|-----------|-------|
| Types / interfaces, error envelope, logging, CLI | N/A | Doc-only plan — correct |
| Naming — supersession `2026_04_11` | Yes (grep) | T1 banner + exec summary; audit: zero `2026-04-11` in `path_to_release.md` |
| Naming — call graph verbatim | Yes (byte compare) | README fenced block matches `architectural-patterns.md:76-78`; orchestration caveat at `README.md:28` |
| Tests | Yes (manual) | §8.1 PowerShell 9-check script; audit rerun 9/9 exit 0 — **not** in CI (Flag 6 deferred) |
| Decision log paths | N/A | No architectural tier — correct |

No hollow *code* contracts (no Python shipped). Residual doc debt is **explicit** in plan §8.4 and CHANGELOG deferred bullets (`path_to_release` §4 E1 vs fixed AUDIT #2; Flag 6 no doc-drift automation) — not silent drift.

### §2 / narrative vs later subtasks

- **No decision logs** — nothing to drift.
- **§0 flag resolutions** (banner not rewrite, T4 gated on P2+P3, #10 grep gate, approval = changelog only) survived in packets and landed edits; scout handoff prose in context-map lines 217–219 was stale until §Post-execution committed in `1e8a66d`.
- **Plan §8.1 “Working tree: clean at implementation SHA”** was false at first audit (P5-F06) — narrative written before closure commit; not repaired in audit text after `1e8a66d`.
- **T3 scope “today (2026-05-25)”** vs T3 commit on 2026-05-30 session — INDEX `Last verified: 2026-05-25` is spec-faithful but calendar-stale relative to closure (audit CR-4, minor).

### Log tiers

| Subtask | Tier | Calibration |
|---------|------|-------------|
| T3 | trivial | OK — changelog append + INDEX date only |
| T1, T2, T4 | standard | OK — grep kill criteria, cross-doc traceability (especially T4); none needed `architectural` |

### Closure vs committed reality

| SHA / artifact | Role | At audit (`153a51f`) | At current `HEAD` (`29145df`) |
|----------------|------|----------------------|-------------------------------|
| `153a51f` | Implementation (T4 + all doc targets) | HEAD; plan v1.0 Active, §8 placeholder | Ancestor |
| — | First audit | `fail` P5-F01, P5-F02, P5-F06 | Audit file unchanged |
| `1e8a66d` | Closure (plan v1.1 + §8, context-map §Post-execution) | N/A (post-audit) | Ancestor |
| `29145df` | Follow-on | — | HEAD |

- **P5-F01 (phase-1/2-class leak):** Plan v1.1 Complete + filled §8 existed only on disk at `153a51f`; `git show 153a51f:plan.md` still had §8 placeholder. **Caught by audit**; **repaired** in `1e8a66d` — not by formal §7 amendment subtasks.
- **Re-audit:** **Not recorded** — audit remains revision 1 `fail` at `153a51f`; no §15 / revision-2 block (contrast phase-1, phase-2, phase-4).
- **§8.1 closure SHA:** Plan text cites implementation SHA `153a51f` and prose “commit containing plan v1.1” without pinning `1e8a66d` — same one-commit-stale class as phase-2 F-11, but lower blast radius (doc-only).
- **Context map scout SHA** `ee870022` vs implementation — expected; §Post-execution in `1e8a66d` mitigates; P5-F02 accepted.
- **MVP_PICKUP.md §204–209:** All four Phase 5 checkboxes still `[ ]` at `HEAD` (P5-F03) — latent hygiene; Phase 4 had T5-amend to fix the same class.

---

## 3. HALTs and amendment cycles

### Executor HALTs

**Count: 0** formal HALTs in commits, CHANGELOG, or executor narrative.

| Situation | HALT? | Assessment |
|-----------|-------|------------|
| T1 CHANGELOG heading `## 2026_04_11` | No | Correct — prerequisite met before edit |
| T1 wet-run risks 1–5 preserved | No | Correct — banner-only |
| T4 Phase 2+3 Complete banners | No | Correct — both plans Complete in HEAD |
| T4 AUDIT #10 vs `aria/llm/client.py` grep | No | Correct — zero `except Exception: pass`; #10 updated with G6 citation, not false-green |
| T4 #19/#20 without Phase 2 artifact | No | Correct — left open per scope |
| T3 `git ls-files` / unstaged diffs on 11 files | No | Correct — approval-only |
| Plan §8 + context-map before commit | No | **Process gap** — should have been closure commit before audit handoff (P5-F01), not executor HALT |

**HALT-shaped improvisation:** None on doc substance. Closure artifacts were improvised on disk after T4 commit, then audit ran against stale HEAD — same pattern as phase-1 F-07 / phase-2 F-01, not kill-criteria bypass.

### Amendment cycles

**Count: 0** — plan §7 empty; no T5-shaped audit remediation subtasks.

- **Audit-driven fix:** Single commit `1e8a66d` (plan + context-map) — remediation without plan §7 amendment row or dedicated packet.
- **First audit pass:** `fail` on process (P5-F01); substance passed adversarial log.
- **Re-audit:** Absent — P5-F01 fix not traced in audit revision 2; merge-ready archive per audit §9 item 1 is satisfied at `HEAD` for plan/context-map but **audit document still says `fail`**.
- **Architectural-tier amendments:** N/A — no architectural tier.

---

## 4. Adversarial pass calibration

### Rejected alternatives that mattered later

- **Full §1 rewrite:** Rejected — banner approach landed; wet-run risks preserved (audit CR-1 accepted).
- **Merge T1+T2:** Rejected — separate commits; rollback-friendly.
- **path_to_release §2–5 in T1:** Rejected — §2–3 still stale post-Phase 3 (Surface 7); correctly out of scope; §4 E1 vs AUDIT #2 remains documented open debt.
- **Skip T3 approval:** Rejected — `[APPROVAL]` + INDEX bump landed.

### Load-bearing assumptions

| Assumption | Held? |
|------------|-------|
| CHANGELOG `## 2026_04_11` underscores | Yes |
| `architectural-patterns.md` call graph stable | Yes (byte match) |
| 11 architecture files tracked, clean diff | Yes |
| Phase 2 + 3 reach Complete before T4 | Yes |
| AUDIT #10 requires G6 / grep, not banner alone | Yes — independent grep, not reliance on Phase 3 banner wording |

### Highest re-plan risk (§5.3: T4)

- **Predicted:** Partial Phase 3 completion; #10 vs G6; false-green on #2/#8/#18.
- **Actual:** T4 executed cleanly — YAMLs populated for #2; #10 gated correctly; #19/#20 left open. **No re-plan.**
- **Trouble elsewhere:** Closure-not-in-HEAD (process), MVP_PICKUP checkboxes, T3 “today” date vs session date, duplicate `29145df` commit message — hygiene, not T4 judgment failure.

---

## 5. Methodology gaps surfaced

### Orchestrator should have prompted for…

- **Closure commit as explicit subtask or kill criterion** before “plan Complete” / auditor handoff — third recurrence of F-01-class defect (phase 1, 2, 5).
- **MVP_PICKUP §204–209 sync** when §1 task statement cites that section — or named deferral in §1 closure criteria (phase 3 deferred G5/G6 boxes; phase 5 deferred all four).
- **Re-audit requirement** when initial audit verdict is `fail` and a closure commit follows — audit file is still the public record at `fail`.
- **Pin closure SHA in §8.1** as distinct from implementation SHA (`153a51f` vs `1e8a66d`) — phase-3 dual-SHA pattern worked; phase 5 prose is ambiguous.

### Executor should have blocked or escalated…

- **Commit plan v1.1 + §8 in same session as T4** (or immediately after) before declaring complete — would have prevented P5-F01 entirely.

### Contracts schema missing or vestigial

- **§2 Tests row as grep-only** is appropriate for doc-only phase but creates **no CI enforcement** — Flag 6 deferred is honest; orchestrator could require “closure subtask runs §8.1 script and commits plan” as standard-tier when Tests = grep script.
- **Packet Definition-of-Done checkboxes** left unchecked in committed packets — vestigial if Landed sections are not used; executor skill expects tiered changelog in `CHANGELOG.md` (landed there for T1–T4).

*Do not edit skills from this file.*

---

## 6. Single sentence verdict

**Partially yes:** The DAG, §0 flag bindings, T4 kill criteria (especially #10 grep and P2+P3 gates), grep-level §2 checks, and tiered CHANGELOG deferrals held for substantive doc intent; the methodology **leaked** on closure discipline (§8/context-map not in HEAD at first audit — same F-01 class as earlier phases), no re-audit to close the audit `fail` loop, and unchecked `MVP_PICKUP` Phase 5 boxes despite landed work.
