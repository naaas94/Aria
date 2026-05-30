# Executor packet — T5-amend · Audit remediation (CHANGELOG + checklist)

**Plan:** mvp-phase4-product-defaults-ux **v1.2**  
**Trigger:** `.dev/audits/2026-05-30-mvp-phase4-product-defaults-ux.md` — F-03, F-06  
**Log tier:** `standard`

---

## §1 Task statement (verbatim)

(Same as plan §1 — this amendment closes audit narrative gaps only; no new phase features.)

---

## §4 Subtask spec

**ID:** T5-amend

**Scope:** Restore tiered changelog for T4; sync MVP_PICKUP Phase 4 checkboxes with landed T2/T4/T3-amend work.

**Files to touch:**
1. `CHANGELOG.md` — `mvp-phase4-product-defaults-ux` section only
2. `.dev/MVP_PICKUP.md` — Phase 4 checklist rows (~197–202) only

**Contract bindings:** None (docs only). Do **not** edit plan §8 (orchestrator fills at Complete).

**Inputs:** T4 landed at HEAD (`test_query_json_placeholder_returns_valid_payload` in `tests/unit/test_cli_entry.py`). T3-amend may land before or after this packet; if QUICK_TODOS checkbox depends on T3-amend, mark it `[x]` only when template subsection exists.

**Outputs:**
- CHANGELOG lists T1, T2, T4, and T3-amend (when landed) under phase-4 heading
- Phase 4 checklist reflects reality

**Kill criteria:**
1. Halt if `test_query_json_placeholder_returns_valid_payload` is missing from `tests/unit/test_cli_entry.py`.
2. Halt if CHANGELOG phase-4 section still has no T4 bullet after edit.

**Log tier:** `standard`

---

## T4 CHANGELOG line (restore from `e06417b`)

Use this wording (or equivalent; must mention `--json`, five keys, `aria_mode`, placeholder env):

```markdown
- T4 (`aria query --json` CLI smoke): Added `test_query_json_placeholder_returns_valid_payload` in `tests/unit/test_cli_entry.py` — invokes `aria query "test question" --json` with `env={"ARIA_PLACEHOLDER_API": "true"}` and asserts exit 0, five `_success_payload` keys, and `aria_mode == "placeholder"`. Rationale: contract coverage for JSON CLI path post–G8 flip without requiring live backends. **Coverage gap (deferred):** `service_unavailable` JSON path not exercised.
```

Insert **after** the T2 bullet, **before** any T3-amend line another executor adds.

---

## MVP_PICKUP Phase 4 checklist (target)

```markdown
- [x] Decide placeholder default for “MVP branch” (**G8**) — flipped code default to `false` on `dev` (T1)
- [x] README Quickstart: explicit “live mode” block with `ARIA_PLACEHOLDER_API=false`
- [x] **QUICK_TODOS:** Local model swap — `LLM_MODEL` / `LLM_BASE_URL` in wet run log template (T3-amend)
- [x] Optional: `aria query --json` smoke in CI via CliRunner (T4)
```

If T3-amend is not yet merged when you run, leave QUICK_TODOS row `[ ]` and note in HALT report — do not check it prematurely.

---

## Resolved inputs

Audit HEAD: `08c12ab`. T2 commit removed T4 from CHANGELOG — restore without removing T2 text.
