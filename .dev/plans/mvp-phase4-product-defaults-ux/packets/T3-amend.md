# Executor packet — T3-amend · Wet run template (append-only)

**Plan:** mvp-phase4-product-defaults-ux **v1.2**  
**Supersedes:** `packets/T3.md` (v1.0–1.1 — do not execute original T3 against a filled session block)  
**Log tier:** `standard`

---

## Continuation note (post-HALT)

T3 **halted** on kill criterion **(2)**: `## Wet run log` already contains the **T6 golden-path session** (2026-05-30). Orchestrator chose **append-only** remediation — **do not modify** text inside the existing session fenced block.

---

## §1 Task statement (verbatim)

Phase 4 resolves the long-standing G8 placeholder-default UX gap (open since the architecture folder was drafted) and improves the operator getting-started experience. Concretely: (1) the code default for `ARIA_PLACEHOLDER_API` is flipped from `true` to `false` so operators who skip the README cannot accidentally believe the system works without backends; (2) the README Quickstart gains an explicit "live mode" block showing `ARIA_PLACEHOLDER_API=false` with the full stack; (3) the wet run log template in `.dev/MVP_PICKUP.md` gains explicit `LLM_MODEL=` and `LLM_BASE_URL=` fields so Phase 1 session data capture is unambiguous; and (4) a `aria query --json` CLI smoke test is added to the unit suite to provide contract coverage for the `--json` code path that currently has zero tests.

**Non-goals:**
- Phase 1–3 and Phase 5–6 MVP_PICKUP items — explicitly out of scope.
- Prometheus / telemetry gaps (G5, G6) — Phase 3.
- Architecture folder commit/approval (G10) — Phase 5.
- Wiring orchestration/MCP into production entry points — Phase 6.
- Full replacement of any eval, nightly, or integration test suite.
- Changing `aria impact --json` behaviour (only `query --json` is in scope).

---

## §2 Shared contracts (T3-amend)

### Env var names (binding)

| Field | Source | Example in template |
|-------|--------|---------------------|
| `LLM_MODEL` | `.env.example` lines 15–16 | `gpt-4o-mini` |
| `LLM_BASE_URL` | `.env.example` lines 15–16 | `https://api.openai.com/v1` |
| `ARIA_PLACEHOLDER_API` | Plan G8 / T1 | `false` for live wet run |

**Retired:** `ollama/llama3.2` as “the” `.env.example` default — use HEAD `.env.example`. Ollama remains valid as a **commented** alternative:

```text
# LLM_MODEL=ollama/llama3.1:8b
# LLM_BASE_URL=http://localhost:11434
```

### Partition constraint (binding)

| Region | Editable? |
|--------|-----------|
| Fenced session block (~lines 251–316, T6 log) | **No** — halt KC(2) if required |
| New `## Wet run log template` section after session | **Yes** |
| Phase 4 checklist (~197–202) | **No** — T5-amend |
| G8 / open-decisions rows | **No** — T1 |

---

## §4 Subtask spec

**ID:** T3-amend

**Scope:** Land explicit `LLM_MODEL=` / `LLM_BASE_URL=` template lines for **future** wet runs without overwriting the T6 session. Consolidate `.dev/QUICK_TODOS`.

**Files to touch:**
1. `.dev/MVP_PICKUP.md` — append-only after the session fence; optional one-line retitle of `## Wet run log (fill on first live session)` (e.g. note that history is below and template is at bottom)
2. `.dev/QUICK_TODOS` — replace with consolidation pointer

**Contract bindings:** Env var names; partition constraint.

**Inputs:** None.

**Outputs:**
- New subsection `## Wet run log template (copy for next session)` with fenced blank scaffold including dedicated `LLM_MODEL=` and `LLM_BASE_URL=` lines
- `.dev/QUICK_TODOS` updated
- `CHANGELOG.md` one-line T3-amend entry under `mvp-phase4-product-defaults-ux`

**Kill criteria:**
1. Halt if template contains `qwen something` or any unresolved model placeholder without `.env.example` values + comment for operator override.
2. Halt if any edit changes the T6 session body inside the existing fenced block (lines with `Date: 2026-05-30`, `Sign-off: Y`, etc.).
3. Halt if the new template fence lacks **both** `LLM_MODEL=` and `LLM_BASE_URL=` as their own lines.

**Log tier:** `standard`

---

## Target template (binding shape)

Insert **after** the closing ` ``` ` of the T6 session (before `## References`):

```markdown
## Wet run log template (copy for next session)

Paste a new fenced block below for each live session. The 2026-05-30 golden-path run is recorded in the section above.

```text
Date:
Environment: (OS, Python version, Neo4j version, Chroma version)
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=https://api.openai.com/v1
# For Ollama: LLM_MODEL=ollama/llama3.1:8b  LLM_BASE_URL=http://localhost:11434 — see .env.example
ARIA_PLACEHOLDER_API=false

aria status →
aria init →
aria ingest →
aria query →
aria impact →
aria telemetry →

Failures / surprises:

Fixes applied (commit refs):

Sign-off (MVP golden path OK? Y/N):
```
```

(Adjust fence nesting in the real file so Markdown renders correctly — outer section uses one fence; inner template uses ` ```text ` as in the existing session style.)

**QUICK_TODOS target:**

```text
# Consolidated into .dev/MVP_PICKUP.md § Wet run log template (Phase 4 T3-amend).
# For local/Ollama model swap: set LLM_MODEL / LLM_BASE_URL in .env — see .env.example.
```

---

## §5 Filtered adversarial context

### Load-bearing assumptions

5. `Phase 1 may fill wet run log before T3 template lands | MVP_PICKUP.md § Wet run log | T3-amend uses append path; must not delete session | T3-amend`

### Hidden couplings

2. `T3 and Phase 1 co-edit MVP_PICKUP.md § Wet run log | session block ↔ template subsection | append-only avoids merge/data loss | T3-amend` — **confirmed**, mitigated

---

## Resolved inputs

T6 session already documents `LLM_MODEL=gpt-4o-mini` in prose — template standardizes **field lines** for the next operator, not retroactive edits to T6.

**Pre-execution:** Read `.dev/MVP_PICKUP.md` from `## Wet run log` through `## References` before editing.
