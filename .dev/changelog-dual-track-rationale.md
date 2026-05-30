# Changelog hygiene — rationale and findings

**Created:** 2026-05-30  
**Status:** Proposed — not implemented  
**Audience:** Owner (tackle when convenient)  
**Related:** Root [`CHANGELOG.md`](../CHANGELOG.md) (tracked; may appear as `CHANGELOG.MD` on Windows)

---

## Problem statement

Root `CHANGELOG.md` has absorbed **executor-tiered** entries (subtask `T1`…`T8`, plan § references, auditor handoff, `.dev/` paths, `MVP_PICKUP` / `AUDIT_DIGEST` sync, `**Coverage gap (deferred):**` tails). That content is valuable for multi-agent audits and phase closure; it is **not** appropriate for a public-facing or operator-facing release log.

Older sections (`## 2026_04_11`, `2026_04_10`, etc.) are closer to the desired public style: feature-oriented headings, code paths, rationale — with some legacy noise (`audit 22`–`30`, `.dev` note links).

---

## Goals

| Goal | Notes |
|------|--------|
| Public changelog | No `.dev/` **paths**; process vocabulary minimized; product/operator signal only |
| Dev changelog | Preserve full executor paper trail (deferrals, F-XX, plan closure, decision-log pointers) |
| Stop re-pollution | Executor packets / tiered changelog norm should target **`.dev/CHANGELOG.md`**, not root |
| Single filename policy | Standardize on `CHANGELOG.md` in docs and cross-links (Windows case-insensitivity is a footgun) |

---

## Recommended approach: two changelogs

| File | Audience | Content |
|------|----------|---------|
| **`CHANGELOG.md`** (repo root) | Operators, contributors, portfolio readers | User-visible changes: `api/`, `aria/`, `README`, `.env.example`, CI, tests. Dated sections + feature headings (mirror `2026_04_11` style). |
| **`.dev/CHANGELOG.md`** (new) | Executors, audits, retrospectives, MVP pickup | Full tiered log: `T{n}`, plan closure, §8 handoff, coverage gaps, audit `F-XX`, SHAs, internal tracker sync. |

**Cross-link (root, one line at top):**

> Detailed implementation / executor log: [`.dev/CHANGELOG.md`](CHANGELOG.md).

**Why split beats “sanitize one file”:**

1. Methodology already instructs append to `CHANGELOG.md` § `phase-X` — retargeting to `.dev/` avoids fighting executors.
2. Audit trail (plan closure, deferred T8, F-03/F-06) stays grep-able in `.dev/`.
3. Public file stays small and stable across phases.
4. Aligns with MVP_PICKUP “repository map” (today one row → should become two).

**Costs:** Two touchpoints at phase end unless you distill dev → public in one pass; one-time migration; update packets, plans §8 artifact lists, audits, MVP_PICKUP.

**Lighter alternatives (rejected for this repo unless scope changes):**

- Single sanitized file — loses paper trail unless git + `.dev/audits/` suffice.
- Dev-only, no public root file — OK pre-1.0; weak for clones that only read root.
- Public file + “Contributors appendix” — process noise still in one scroll.

---

## Editorial principles (public root)

| Keep | Drop or reframe |
|------|------------------|
| User-visible behavior and test paths | Literal `.dev/…` paths |
| Phase **names** when useful (`observability`, `eval honesty`) | `§8 auditor handoff`, `orchestrator`, `context-map`, `kill criteria`, `plan Flag N` |
| Optional one-line verification (`56 tests passed`) | Commit SHAs unless you want release archaeology |
| Spell out goals once (`placeholder default`) vs bare `G8` | `MVP_PICKUP`, `AUDIT_DIGEST`, `audit F-03` |
| `audit 22`–`30` in older sections — optional product audit trail | Bullets that only sync internal trackers or fix CHANGELOG itself |

---

## Audit findings — `.dev/` path references (root file)

**15 literal `` `.dev/…` `` hits** (as of 2026-05-30 review):

| Line | Snippet / topic |
|------|-----------------|
| 7 | `.dev/AUDIT_DIGEST.md` |
| 13 | `.dev/architecture/aria/INDEX.md`, `changelog.md` |
| 17 | `.dev/decision-logs/T1-g8-placeholder-default.md` |
| 23 | `.dev/QUICK_TODOS` |
| 25 | `.dev/MVP_PICKUP.md` |
| 29 | `.dev/plans/phase-3-observability/plan.md` |
| 50 | `.dev/decision-logs/T2-requires-multi-hop.md` |
| 58–60 | plans, context-map, audits, MVP_PICKUP, decision-logs |
| 166, 215 | `.dev/notes_prod_or_changes.md` |
| 184 | `.dev/notes_for_prod_or_changes.md` (+ **broken** markdown links) |

**Implicit internal references (no path, still dev-facing):** `path_to_release`, `architectural-patterns.md` (file lives under `.dev/architecture/aria/`), `context-map`, `MVP_PICKUP`, `open-questions Q3`, `AUDIT_DIGEST`.

---

## Audit findings — process / meta bullets

**Strong candidates to move to `.dev/CHANGELOG.md` only (or delete from public):**

| Line | Section | Reason |
|------|---------|--------|
| 7 | `## — 2026-05-30` | AUDIT_DIGEST open-table sync only |
| 13 | same | Architecture folder G10 approval / INDEX bump |
| 25 | product-defaults-ux | CHANGELOG + MVP_PICKUP checklist meta; audit F-03/F-06 |
| 29 | observability | Plan closure + §8.1–§8.5 auditor handoff + orchestrator gate |
| 58 | golden-wet-run | Plan closure + §8 + committed audit artifact |
| 59 | golden-wet-run | Audit contract reconciliation vs plan §2 Amendment |

**Sanitize in place (keep bullet, trim tails):** Most other lines in `2026-05-30` blocks — remove `**Coverage gap (deferred):**` (24 occurrences), `plan Flag 6`, `audit F-XX`, `§2 Amendment`, `context-map Flag N`, executor cross-refs like `deferred to T8`.

**Plan closure (user preference):** May stay in **dev** log as one line per phase, e.g. “Phase 3 observability — plan complete; 56 tests.” No §8 subsection numbers in public.

---

## Section structure issues (root)

| Issue | Lines | Suggestion |
|-------|-------|------------|
| Untitled `## — 2026-05-30` | 5–13 | Rename e.g. `## doc-hygiene — 2026-05-30` or fold into public `### Documentation` |
| Executor `T{n}` headings vs `### CLI` | 5–65 vs 109+ | Normalize May block to feature titles |
| Intro line 3 | 3 | “tracked in this folder” / future root changelog — replace with standard Keep a Changelog opener + link to `.dev/CHANGELOG.md` |
| Self-reference | 11, 25 | `CHANGELOG.md` vs `CHANGELOG.MD`; bullet that only fixes CHANGELOG |
| Broken links | 184 | `(notes_for_prod_or_changes.md)` does not resolve; drop bullet or fix when promoting notes |

---

## Public changelog sketch (May 2026 — distill, don’t copy)

After split, root might look like:

```markdown
## 2026-05-30

### Observability
- Prometheus: HTTP/graph duration histograms, LLM cost counter, ingestion duration; G6 telemetry write errors on LLM path.
- `TelemetryStore.cost_by_request`; tests in test_metrics, test_llm_telemetry, test_telemetry_store.
- Docs: Ollama zero-cost expectation in README / .env.example.

### Eval honesty
- Removed always-pass `multi_hop_declared` stub; `test_runner_unit.py` + CI gate.
- Synthetic `retrieved_context` for medium-tier goldens; GDPR replay golden (q6).

### Product defaults & UX
- `ARIA_PLACEHOLDER_API` default **false**; README live-mode quickstart; `aria query --json` smoke test.

### Documentation & hygiene
- README production call graph; path-to-release §1 supersession banner; architecture pack last verified 2026-05-25.
```

(Process-only rows from lines 7, 13, 25, 29, 58, 59 live in `.dev/CHANGELOG.md`.)

---

## Wiring changes (implementation checklist)

- [ ] Create `.dev/CHANGELOG.md` — move lines **5–65** (and any other process-heavy blocks) largely as-is; optional later pass to strip paths even in dev log.
- [ ] Rewrite root `CHANGELOG.md` — public distill for May phases; keep `2026_04_*` (trim `.dev` note links on 166, 184, 215 if desired).
- [ ] Add one-line pointer at top of root → `.dev/CHANGELOG.md`.
- [ ] Update [`.dev/MVP_PICKUP.md`](MVP_PICKUP.md) repository map: two rows (release vs implementation log).
- [ ] Update executor packets / orchestrator skill norm: tiered changelog → **`.dev/CHANGELOG.md` § `phase-X`** only; optional one short public bullet per phase at closure.
- [ ] Grep repo for `CHANGELOG.md` § `phase-` and plan §8 artifact paths; align audits and retrospectives.
- [ ] Add contributor rule (README or `.dev/` note): no `.dev/` paths in root changelog; no §/auditor handoff in public.

---

## Sanitization stance options (pick one when editing)

| Stance | Action |
|--------|--------|
| **A — Aggressive** | Drop process-only bullets from public; remove all coverage-gap tails |
| **B — Moderate** | Split files; public distill; dev keeps full tails |
| **C — Minimal** | Split files; public only loses `.dev/` paths + §8/orchestrator lines |

**Recommendation:** **B** via two-file split (matches dual-track above).

---

## Easy-to-miss items

1. **Git tracks `CHANGELOG.md`** — unify casing in all references.
2. **`architectural-patterns.md`** — referenced by name in line 9; file is under `.dev/architecture/aria/`.
3. **`path_to_release.md`** — under `.dev/`; public bullet can say “release readiness doc §1”.
4. **Wet-run bullet (line 60)** — high product value; strip only log locations.
5. **`audit 22`–`30`** in `2026_04_10` — different from `audit F-XX`; decide if public keeps numbered audit IDs.
6. **`TASK 2` / `TASK 7`** in `2026_04_11` — older executor labels; optional rename for consistency.
7. **Architecture `changelog.md`** — separate from product changelog; don’t confuse with `.dev/CHANGELOG.md`.
8. **Future phase 6+** — without retargeting packets, root will fill with process again.

---

## Reference: primary delete / rewrite targets (root, if staying single-file)

| Line | Action |
|------|--------|
| 7, 13, 25 | Delete from public (or move to dev only) |
| 29 | Rewrite to one-line phase complete (public) or dev only |
| 58, 59 | Dev only |
| 184 | Delete or fix links; don’t point readers into `.dev/` from root |

---

## Decision log

| Date | Decision |
|------|----------|
| 2026-05-30 | Document audit + propose **dual changelog** (root public, `.dev/` implementation). No repo changes applied in this pass. |

---

## Next session

1. Choose stance A / B / C.  
2. Create `.dev/CHANGELOG.md` and migrate May 2026 blocks.  
3. Distill public root (sketch above).  
4. Update MVP_PICKUP + packet template grep.
