# Learning retrospective — Phase 5 doc & architecture hygiene

**Date:** 2026-05-30  
**Task:** `phase-5-doc-architecture-hygiene` — close MVP pickup §204–209 (criterion 6: “docs match code”): supersede stale `path_to_release` CLI narrative, add README production call graph, acknowledge `.dev/architecture/aria/` as reviewed SSOT, sync `AUDIT_DIGEST` after eval-honesty and observability phases land.  
**Produced:** Four implementation commits T1–T4 (`614fcf2` → `855abcb` → `4fe003b` → `153a51f`), closure + audit + plan v1.1 §8 in `1e8a66d`; adversarial audit **fail** on process only (`.dev/audits/2026-05-30-phase-5-doc-architecture-hygiene.md` — P5-F01 closure not at implementation SHA until later commit); no decision logs (plan §2: no architectural tier). Verification: §8.1 PowerShell grep script **9/9** at `153a51f`; no pytest.

**Why this qualified:** Doc-only phases still sit on integration seams (AUDIT rows ↔ YAML fixtures ↔ `aria/llm/client.py`, README ↔ `architectural-patterns.md`, supersession banners ↔ CHANGELOG heading slugs). The pre-plan map catalogued eight coupling surfaces and six CONDITIONAL flags; T4’s external gate and #10/G6 coupling are the kind of “false green” trap that only shows up when documentation is treated as truth, not decoration. Worth capturing how hygiene work differs from Phases 2–4 and why the same closure-commit habit keeps recurring.

---

## 1. Task context

Pre-plan exploration at scout SHA `ee870022` produced a **CONDITIONAL** context map (flags on path_to_release strategy, AUDIT edit timing, architecture “commit vs approve,” README placement, AUDIT #10 vs G6, missing doc-drift tests). The orchestrator resolved all six in plan §0 before packets: banner not rewrite; T4 only after Phase 2 and Phase 3 plans show Complete; architecture approval = `[APPROVAL]` changelog entry + INDEX date bump, not editing the eleven content files; README gets both verbatim call graph and orchestration caveat; #10 row gated on grep of `aria/llm/client.py`, not on the Phase 3 banner alone.

Execution DAG: parallel **path_to_release banner**, **README call graph**, and **architecture acknowledgment** (any order) → **AUDIT_DIGEST sync** blocked on external Phase 2 + Phase 3 Complete. Landed in that commit order with CHANGELOG bullets per subtask. Plan §8 documents byte-level contract evidence and deliberately leaves `path_to_release` §4 E1 vs fixed AUDIT #2 as open cross-doc debt.

Audit at `153a51f` found implementation substance correct but **fail** because plan v1.1 + §8 and context-map §Post-execution lived only on disk until `1e8a66d`. `MVP_PICKUP.md` §204–209 checkboxes remain `[ ]` at audit time (P5-F03) — ironic for the phase whose job is doc hygiene.

---

## 2. What I now understand that I didn't before

### “Docs match code” is a falsifiability problem, not an editing problem

Phase 5 does not make prose prettier; it removes **claims that a cold reader would believe and that code contradicts**. The highest-risk work was T4 (AUDIT table sync): moving row #2 to “fixed” while retrieval YAMLs were still empty would have been a false green story (context map Surface 3). The plan’s fix is not “be careful” but **kill criteria**: Phase 2 Complete banner + spot-check artifacts + leave #19/#20 open when no Phase 2 citation exists. I now treat audit digests like test suites: every “fixed” row needs a traceable artifact (commit, CHANGELOG, plan §8), not narrative confidence.

### A “Complete” plan banner is insufficient for doc gates tied to code

§0 Flag 5 and T4 kill criterion 5 exist because **Phase 3 Complete ≠ G6 landed** in the general case. AUDIT #10 (“silent except” on telemetry writes) couples to `aria/llm/client.py`, not to middleware copy in the digest. The executor must grep `except Exception: pass` independently. That generalizes: whenever documentation sync is gated on another phase, assume the other phase’s closure artifact is **process-complete**, not **semantically-complete** for your row.

### Banner supersession is a first-class pattern for stale SSOT sections

Rewriting 47 lines of `path_to_release` §1 would have dropped wet-run risks 1–5 that are still useful historical context. The banner + executive-summary strike-through satisfies MVP criterion 6 at lower risk: current truth at the top, preserved archaeology below. The tradeoff is intentional cognitive load — readers who skip the blockquote still see “no CLI module” in the body (audit CR-1). Hygiene is not always “make every sentence current”; sometimes it is **label staleness explicitly** and link to `CHANGELOG.md` `## 2026_04_11`.

### Naming contracts matter for cross-doc links

§2 froze supersession dates as `2026_04_11` (underscores) because that is the actual CHANGELOG heading slug; hyphens would point at nothing. That is a small detail with a large failure mode (T1 cross-ref broken forever). Doc phases need the same rigor as API symbol names when strings are identifiers, not prose.

### Architecture folder “approval” is governance, not a git event

All eleven files were already tracked at scout SHA. G10 in MVP pickup meant **owner acknowledgment as SSOT**, recorded in `architecture/changelog.md` and `INDEX.md` `Last verified`, not a force-commit of content the executor did not review. That matches the project-architecture skill’s ownership model and avoids fake “we committed the folder” when the real act is human review.

### Production call graph is a single sentence with three audiences

README’s `## Architecture` ASCII diagram still shows a multi-agent orchestrator on the FastAPI path (audit CR-2, accepted non-goal). T2 added verbatim fenced lines from `architectural-patterns.md` plus a parenthetical on the **Orchestration** paragraph because Surface 5 was **confirmed**: call graph alone would leave two contradictory stories in one section. Onboarding docs need **explicit “not on the production path”** language when test-heavy subsystems share marketing diagrams with live traffic.

### Doc-only verification is grep contracts, not pytest absence

Plan §2 says no pytest; §8.1 is a nine-check PowerShell script (banner present, hyphen form absent, call graph strings, `[APPROVAL]`, AUDIT row patterns, no bare-except in client). That is the doc-phase equivalent of golden tests: cheap, repeatable, not in CI yet (Flag 6 deferred). The audit re-ran the script and passed — substance was verifiable without importing `aria`.

### Scout context maps go stale by design

P5-F02 is expected: map header SHA `ee870022`, implementation `153a51f`, handoff notes still describing pre–Phase 3 code (`except Exception: pass`, missing G5). The auditor is told to use plan §8 and code, not scout prose. I was treating map staleness as a defect; it is **a timestamped snapshot** plus optional §Post-execution. The learning is: never file a finding against scout claims on files that diverged — qualify and re-verify.

### Residual cross-doc debt can be explicit and still “phase complete”

`path_to_release` §4 E1 still narrates empty-context eval failure while AUDIT #2 is fixed (plan §8.4 open). T1 scope was §1 only by design. Phase complete does not mean **all related docs are consistent**; it means the scoped contract rows are closed and remaining debt is logged. That is different from Phases 2–3 where “open” usually meant missing code.

---

## 3. Decisions I would make again

**Resolve all six CONDITIONAL flags in plan §0 before writing packets.** Banner vs rewrite, T4 timing, approval semantics, README placement, #10 gate, Flag 6 deferral — executors did not re-litigate during T1–T4.

**Banner approach for path_to_release §1.** Preserves wet-run risks; cross-links CHANGELOG `2026_04_11`; matches MVP pickup wording (“OR add banner”).

**Hard external gate on T4 (Phase 2 + Phase 3 Complete).** Prevents AUDIT sync on incomplete eval/observability stories.

**Grep `aria/llm/client.py` before touching AUDIT #10.** Correct even when Phase 3 plan says Complete; honors G6 as code truth.

**Parallel T1 / T2 / T3.** Disjoint files, no symbol overlap, faster wall time.

**Leave AUDIT #19 and #20 open.** “Not in Phase 2 scope” is honest; closing without artifacts would repeat the false-green failure mode Surface 3 warns about.

**Verbatim call graph from `architectural-patterns.md`.** §2 binding prevented invented service names.

**Record coverage gaps in CHANGELOG per subtask.** Flag 6 deferral is visible four times; future-me knows drift detection was conscious, not forgotten.

**Principle that generalizes:** For doc phases, **decide truth conditions in §0, verify with grep-level contracts in §8, and log deliberate non-goals in §8.4** — same shape as freezing metric labels in Phase 3.

---

## 4. Decisions I would change

**Commit plan v1.1 + §8 and context-map §Post-execution in the same commit as T4 (or immediately after).** P5-F01 is the same class as Phase 1–3 closure-not-at-HEAD: implementation SHA `153a51f` is not auditable in isolation for “phase complete.” `1e8a66d` fixed it, but the gap created audit **fail** and archaeology confusion. **Better rule:** last subtask commit *or* dedicated closure commit within minutes — never “docs landed, plan closure on disk over the weekend.”

**Check off `MVP_PICKUP.md` §204–209 in the closure commit.** P5-F03: the phase whose purpose is pickup alignment left its own checklist unchecked. Phases 2 and 3 deferred pickup to Phase 5; Phase 5 deferred pickup to … nothing yet. **Better rule:** any phase that cites MVP pickup items must flip those checkboxes in the closure PR unless an item is explicitly deferred with a cross-link.

**Align T3 `Last verified` with execution date.** Spec said “today” at T3; landed `2026-05-25` while CHANGELOG phase-5 work is `2026-05-30` (audit CR-4). Minor, but it undermines the stamp’s meaning.

**Consider one extra subtask or T1 scope expansion for path_to_release §4 E1.** Plan non-goal was defensible for timeboxing; leaving eval narrative stale while AUDIT #2 is fixed will confuse the next operator running goldens. Either a one-line supersession in §4 or a pickup bullet “E1 narrative deferred” would cost little.

**Underlying error on closure/pickup:** Still treating **orchestrator artifacts and roadmap checkboxes** as lower priority than file edits, even on a doc hygiene phase.

---

## 5. Patterns in my own thinking

**Repeated “implementation done, plan closure later.”** Four MVP phases, same audit finding family. The grep script passed at `153a51f`; the plan at that SHA still said §8 placeholder. I am optimizing for visible doc diffs, not for **git as the audit trail**. The discomfort here is that I know the pattern and still reproduced it.

**Deferred MVP_PICKUP across phases until the hygiene phase — then skipped hygiene on the hygiene checklist.** Phase 2 learning note warned future-me would re-read stale pickup; Phase 5 was supposed to fix that and left §204–209 open. Motivated reasoning: “the plan §8.4 table documents status” is not the same as a checkbox a human scans.

**Underestimated doc phases’ seam complexity because there was no pytest.** T4 required the same rigor as wiring metrics: external gates, code grep, artifact traceability. I mentally bucketed Phase 5 as “easy day” because no `aria/` edits; the audit’s mandatory integration-seams focus was appropriate.

**Accepted contradictory README diagram with clear eyes.** Correct trade for scope, but I should notice when **non-goals accumulate** into onboarding hazard (diagram + prose + call graph = three layers). A future pass might add one diagram caption, not a full rewrite.

**Trusted orchestrator §0 resolutions** on banner and #10 gate — worked. Less trust warranted on **process closure**; that part I keep outsourcing to “later commit.”

---

## 6. Open questions

- When does Flag 6 (automated doc-drift) earn a CI job — grep script from §8.1, markdown link checker, or AUDIT↔CHANGELOG row diff? What is the cheapest test that would have caught T3 date drift or a removed banner?
- Should `path_to_release` §2–3 get a Phase 5.5 pass now that Phase 3 metrics landed, or stay frozen until another observability doc task?
- Is one caption on the README ASCII diagram enough to reconcile CR-2, or does the diagram need a separate “test / scratch” figure?
- Should supersession banners be the **standard** pattern for all `.dev/*` historical narratives (telemetry-audit, path_to_release §4), with a repo-wide date-format lint for `2026_MM_DD`?
- After Phase 6, does `architectural-patterns.md` remain the single source for the call graph, or should README include only a link (DRY vs onboarding skim)?

---

## 7. Single paragraph synthesis

Phase 5 taught me that **documentation hygiene is falsification work**: AUDIT rows, README call graphs, and supersession banners are only valuable when each “fixed” or “current” claim can be defeated by grep or artifact lookup — and that T4’s coupling to Phase 2 YAMLs and Phase 3 G6 code is the same false-green class as eval goldens or silent telemetry, just without pytest. The orchestrator pattern (CONDITIONAL flags frozen in §0, parallel disjoint edits, strict external gate, explicit open debt in §8.4) fit doc-only work well; my recurring mistake is unchanged from Phases 1–3: I ship the file diffs, pass the grep script, and treat plan §8 plus MVP pickup checkboxes as follow-up paperwork, which breaks audit archaeology and leaves the roadmap lying about the phase that was supposed to fix lying roadmaps. The compounding takeaway: for any “docs match code” tranche, **closure commit + pickup checkboxes are part of the deliverable**, not metadata — and when in doubt, grep the code row before moving the digest row.
