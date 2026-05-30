# Methodology retrospective — mvp-phase1-golden-wet-run

## 1. Task identifier

**Task:** mvp-phase1-golden-wet-run (Phase 1 golden-path wet run)  
**Date:** 2026-05-25 (plan) · execution/amendment 2026-05-30  
**Plan versions:** v1.0 → v1.1 (audit-driven amendment)  
**Skills:** orchestrator-planning v0.6, pre-plan-exploration v0.2, executor-subtask-execution, auditor-review v0.4  
**One line:** Resolve five pre-run blockers (T1–T5), execute live CLI golden path (T6), audit, then reconcile contracts and close the plan (T7–T8).

---

## 2. Plan vs reality

### DAG vs execution

- **Planned:** `{T1..T5}` parallel → T6 sequential; amendment `T6 → T7 → T8`.
- **Actual:** T1–T5 ran as **separate commits** in one session (order: T1, T2, T5, T4, T3 — not strictly parallel agents, but no file conflicts). T6 after all five. T7 then T8 after audit **fail**.
- **Unsafe parallelization:** None observed; DAG held.
- **Deviation:** T6 did not halt on kill criterion (a) when Chroma compose health stayed `unhealthy` — operator continued because v2 heartbeat returned 200. Documented in wet run log and decision log; reasonable interpretation but **not** a literal kill-criteria halt.

### Contracts at implementation surface

| §2 surface | Enforced in code + test? | Notes |
|------------|-------------------------|-------|
| `sample_regulation.html` | Yes (T6 ingest exit 0) | — |
| integration marker + command | Yes (25 pytest) | — |
| serve `API_PORT` / 8080 | Yes (`test_serve.py`) | Shipped **after** plan said "no automated test" until §2 Amendment |
| regulation_ids stdout | Yes (`test_ingest_command.py` + wet run) | Literal differed from §2 until amendment |
| status LLM note | Yes (`test_status.py`) | Literal differed from T5 spec until amendment |
| ingest preflight vs `/ready` | Manual evidence only | T6 kill criteria met via log; F-08 still open |
| §2 "No new test files T1–T5" | **Hollow until T7** | Three unit files added in T3–T5 commits; green tests masked contract drift until cold audit |

**Hollow-contract window:** From T3/T4/T5 commits through `d448a31`, shared §2 Tests row was false while behavior was beneficial. Amendment + unit tests fixed binding; original §2 L95 left intentionally with supersession note (CR2-01).

### §2 / decision-log narrative vs later subtasks

- **T5 spec quote** vs shipped `status.py` — drift repaired in T7 §2 Amendment Logging, not by reverting code.
- **T4 `(none — …)` suffix** — extended in code before amendment; T7 copied HEAD literals into plan.
- **CHANGELOG** acknowledged T4 unit tests at execution time; T3/T5 test files **not** narrated until T7 — audit flagged mild narrative-concealment (F-02/F-03).
- **Decision log T6** remained accurate post-T7/T8; no stale prose after amendment.
- **Original §2 rows** still visible above §2 Amendment; amendment explicitly supersedes — drift **repaired at audit + T7**, not silently ignored.

### Log tiers

| Subtask | Tier | Calibration |
|---------|------|-------------|
| T1, T5 | trivial | OK |
| T2, T3, T4 | standard | OK — real code + tests |
| T6 | architectural | OK — wet run + decision log |
| T7, T8 | standard | OK — doc/contract work; could argue T7 was **under-tiered** as contract-architecture, but scope was bounded |

### Closure vs committed reality

- **Closure SHA:** Plan §8.1 records `5df123f` (T7); git tip for phase is `19e35ca` (T8 doc-only). Re-audit noted R2-F-01 (observation): §8.1 tree SHA ≠ closure commit — **intentional** per plan risk note; not latent failure.
- **First commit with all T1–T6 code artifacts:** `d448a31` (T6 includes docs; code in prior commits).
- **Audit rev 1** at `d448a31`; **rev 2 pass** at `19e35ca`.
- **§8.2 artifacts:** present-in-HEAD at `19e35ca` per re-audit checklist.
- **Context map:** scout `ee870022` vs closure documented in §Post-execution (F-01 closed).
- **First audit** ran on **clean** tree at `d448a31`; re-audit noted **dirty** unrelated files but verified on committed HEAD — good discipline, minor process noise.
- **Post-closure:** working tree has unrelated mods (`aria/health`, `aria/llm`, etc.) — outside phase scope; not a closure defect.

---

## 3. HALTs and amendment cycles

### Executor HALTs

**Count: 0** formal HALTs recorded in decision logs or changelogs.

| Situation | HALT? | Assessment |
|-----------|-------|------------|
| T3–T5 added unit tests not in packet §Files to touch | No | **Should have escalated** or updated §2/changelog per file — silent scope widen |
| T6 Chroma compose unhealthy | No | Documented workaround; kill (a) ambiguous for "functional vs compose health" |
| T6 Ollama timeout → OpenAI fallback | No | Valid operator path; decision log documents |
| T6 no code fixes | No | Correct — no >3-file re-plan trigger |
| T7/T8 kill criteria | Not triggered | Amendment landed cleanly |

**HALT-shaped improvisation (no escalation):**

- Unit tests in T3–T5 treated as local quality wins without contract update until audit — **papered over** until T7, not executor HALT.
- T6 signed off **Y** while plan still **Active** and §8 empty — **process gap (F-07)** closed by T8, not by halting T6.

### Amendment cycles

- **One amendment wave:** v1.1 → T7 (contract reconciliation) + T8 (closure + context map + audit commit).
- **Scope:** Right-sized — document landed tests/literals; no revert; no F-08 replay script.
- **Closure:** Re-audit **pass** on first amendment pass (rev 2 in same audit file).
- **Residual:** F-08, invalid `API_PORT`, Neo4j read-failure paths explicitly **open** in §8.4 — appropriate deferral.

---

## 4. Adversarial pass calibration

### Rejected alternatives that mattered later

- **Merge T3/T5 into T6:** Would have blocked serve step — validated; pre-run split was correct.
- **Use `tests/eval/e2e` for pytest command:** Not needed; T2 aligned documented command.
- **Revert unit tests (amendment §5):** Rejected in T7 — correct; tests were the fix for F-02.
- **seed_corpus primary ingest:** Avoided in T6 — Flag 4 coupling held.

### Load-bearing assumptions

| Assumption | Held? |
|------------|-------|
| LLM reachable during wet run | **Partially** — Ollama failed 12s probe; OpenAI fallback worked (documented) |
| Regulation `.id` key | **Yes** — audit disproved suspected mismatch |
| html_parser generic HTML | **Yes** |
| Typer serve port env default | **Yes** — Pattern B |
| Entity extractor creates Regulation nodes | **Yes** — wet run printed IDs |
| Integration tests mocked / no live infra | **Yes** — 25 passed; operator hazard when `ARIA_PLACEHOLDER_API=false` leaked into pytest |

### Highest re-plan risk (§5.3: T6)

- **Predicted:** LLM stall, empty regulation IDs.
- **Actual:** LLM env surprise (Ollama tag/timeout) — **recovered in-session** without re-plan; regulation IDs present; impact chain empty (data gap, documented F-09).
- **Process surprise:** Contract drift from T3–T5 tests — caught by **audit**, not T6 — trouble came from **executor/plan sync**, not runtime golden path.

---

## 5. Methodology gaps surfaced

### Orchestrator should have prompted for…

- **Explicit "beneficial drift" path** when executors add tests/files forbidden by §2 — e.g. mandatory changelog + §2 stub update in same commit, or a micro-subtask "contract touch" before merge.
- **§7 amendment template** in v1.0 plan when §2 says "no new test files" but subtasks are standard tier — predict F-02 class findings.
- **Kill-criteria glossary** for infra health (compose `healthy` vs functional heartbeat) before T6 architectural run.

### Executor should have blocked or escalated…

- Shipping `tests/unit/test_{serve,ingest_command,status}.py` without updating packet §Files to touch, plan §2, or CHANGELOG for T3/T5 — **contract violation that audit had to find**.
- Closing T6 with plan Status still **Active** — T6 packet listed decision log + wet run but not plan Status; orchestrator/executor handoff to §8 closure was **implicit** and missed until F-07.

### Contracts schema missing or vestigial

- **Supersession pattern** (§2 Amendment) worked well once added; original rows left in place require auditors to read amendment — OK but easy to misread without rev-2 discipline.
- **"No separate test; wet run observes"** rows become vestigial quickly when executors add unit tests — either ban tests in spec or require immediate §2 update.
- **F-08 / manual wet-run evidence** has no contract hook for "evidence artifact type" (log vs script vs CI) — deferred correctly but remains a recurring gap.

*Do not edit skills from this file.*

---

## 6. Single sentence verdict

**Partially yes:** The DAG, kill criteria (runtime), adversarial assumptions, and amendment loop (T7/T8 → re-audit pass) held up; the methodology **leaked** on executor–contract sync (unit tests and stdout literals shipped without updating §2/packets/CHANGELOG until audit) and on T6→closure handoff (F-07), which audit and amendment repaired in one cycle without re-planning the golden path.
