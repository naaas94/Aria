# Decision log — G8: placeholder_api_enabled default

**Subtask:** T1 (mvp-phase4-product-defaults-ux)  
**Date:** 2026-05-30  
**Status:** Landed

## Decision

Flip `ARIA_PLACEHOLDER_API` code default from `"true"` to `"false"` in `api/config.py`.

## Rationale

Phase 4 targets operator UX on `dev`: operators who skip the README should not get synthetic answers that look like a working compliance stack. Defaulting to live mode surfaces missing Neo4j/Chroma/LLM clearly (503 / preflight) instead of silent placeholder data. Nightly CI already sets `ARIA_PLACEHOLDER_API=false` explicitly and is unchanged.

## Alternatives rejected

1. **Document-only** (keep code default `true`, add README live-mode block) — rejected because the code default would still mislead anyone who never reads docs; G8 is a product default decision, not documentation-only.
2. **Flip only on a release branch** — rejected because this plan lands on `dev` per Flag 2 resolution; deferring the flip would leave README/T4 work blocked on an ambiguous branch policy.

## Assumptions

- Unit tests that mount `api.main:app` must set `ARIA_PLACEHOLDER_API` explicitly when they assume placeholder behavior. Initial T1 HALT proved `tests/unit/test_metrics.py` `client` fixture needed `monkeypatch.setenv("ARIA_PLACEHOLDER_API", "true")` before app import (T1-amend).
- `.dev/decision-logs/` is writable and not blocked by `.gitignore`.
- E2E `test_live_queries.py` callers that need placeholder mode will set `ARIA_PLACEHOLDER_API=true` explicitly (docstring updated; test logic unchanged).

## Deferred items

- Nightly CI already sets `ARIA_PLACEHOLDER_API=false` — no change needed.
- `test_live_queries.py` docstring updated (minor); test logic unaffected.
- Architecture `public-interface-inventory.md` lists `placeholder_api_enabled` as "stable" — still stable; default value change does not alter the public signature. G10 (architecture folder commit) is a Phase 5 item.
- No unit test asserts `placeholder_api_enabled()` returns `False` when `ARIA_PLACEHOLDER_API` is unset (deferred per §2 Tests; T4 CLI smoke uses explicit env only).
