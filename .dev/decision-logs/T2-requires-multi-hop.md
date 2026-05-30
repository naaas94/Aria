# T2 — `requires_multi_hop` stub removal

**Plan:** phase-2-eval-honesty v1.0  
**Subtask:** T2  
**Date:** 2026-05-30

## Decision

Remove the `sub["multi_hop_declared"] = True` always-pass stub from `run_retrieval_check` in `tests/eval/golden_set/runner.py`.

## Context

`ExpectRetrieval.requires_multi_hop` is set on medium-tier retrieval YAML cases to document multi-hop intent. Lines 198–199 previously set `sub["multi_hop_declared"] = True` whenever the flag was true, adding a sub-check that always passed and inflated pass confidence without validating hops, trace, or graph expansion.

Pre-removal grep (`multi_hop_declared`, Python only): only `runner.py` contained the string; no readers in `report.py`, `eval_store.py`, or tests.

## Alternatives rejected

1. **Implement real multi-hop validation** (trace metadata, hop count, graph-expanded context) — no trace/hop fields exist on retrieval YAML `input` today; would need schema and fixture contract work outside Phase 2 scope.
2. **Keep stub but rename key** (e.g. `_metadata_only`) — still serializes a misleading passing sub-check; removal is clearer.
3. **Remove `requires_multi_hop` from schema and YAMLs** — heavier churn across q1–q5; field retains documentation value for future validation.

## Chosen approach

Remove stub only. Retain `requires_multi_hop` on `ExpectRetrieval` as declarative metadata with no validator. Add `tests/eval/golden_set/test_runner_unit.py` to lock retrieval pass/fail behavior and prove the flag does not affect `CheckOutcome.passed`.

## Assumptions made

- No downstream code asserts on `multi_hop_declared` in serialized reports (grep-confirmed for Python).
- Context-map Flag 4 is resolved as **remove stub** per plan §0 (not implement validation in T2).

## Items deferred

- **Real `requires_multi_hop` validation** — blocked until retrieval case `input` carries trace/graph hop evidence and a contract for expected hop semantics.
