# Evaluation & CI — QA audit report

_Generated audit notes: golden-set pipeline, eval store, CI matrix vs nightly, security/golden overlap._

## Executive summary

- **Golden-set plumbing is coherent** (manifest sync, tier skipping, `GoldenReport` with `run_id`-scoped correlation IDs, JUnit `correlation_id` properties, optional `EvalStore`). **Quality** checks are **keyword/heuristic** only (`run_quality_check`, `run_retrieval_check`); they do not prove retrieval correctness or multi-hop graph behavior.
- **CI “fast” golden tier intentionally skips all `medium` cases** (the five retrieval YAMLs). The CI job name **“includes replay” is misleading**: there are **no** `expect.replay` cases and `replay/` only contains `.gitkeep`.
- **Eval offline store**: JSONL under `tests/eval/eval_runs/` (gitignored), **only populated when `--emit-eval-store`** (nightly only). Records mirror `case.input`; **no scrubbing** unlike `recorder.py` replay capture. **`_response` / `_trace`** are only stored if present in YAML input.
- **CI vs codebase drift (verified locally)**: OpenAPI exposes `/metrics` and `/telemetry` (`api/routers/telemetry.py`, `api/main.py`), but **`test_documented_openapi_paths_match_expected_set`** in `tests/eval/test_security_audit.py` and **`security-openapi-paths`** golden YAML still expect the **older eight-path** set — golden + contract security tests fail until expectations are updated.
- **Nightly golden run**: **`--golden-tier=slow` runs `medium` retrieval cases**, which use **empty `retrieved_context`** and **fail** the retrieval lens (`run_retrieval_check`). **Verified locally** for `retrieval-q1`. Nightly “Golden set (all tiers)” is likely **red** unless cases/fixtures are fixed or tier selection changes.
- **Nightly runs the full golden suite twice** (dedicated step then `pytest tests/eval/`), which **duplicates work** and **overwrites** `golden_report.json` / `.xml` with the second run.

## Scope map

| Area            | Paths                                                                 |
|-----------------|-----------------------------------------------------------------------|
| CI PR           | `.github/workflows/ci.yml`                                            |
| Nightly         | `.github/workflows/nightly.yml`                                       |
| Security workflow | `.github/workflows/security.yml` (pip-audit only; not eval)         |
| Golden driver   | `tests/eval/golden_set/test_goldens.py`, `conftest.py`, `loader.py`, `manifest.yaml`, `cases/**/*.yaml` |
| Lenses          | `tests/eval/golden_set/runner.py` (`run_*_check`)                     |
| Reports / correlation | `tests/eval/golden_set/report.py` (`GoldenReport`, `CaseResult`) |
| Replay          | `tests/eval/golden_set/recorder.py`, `run_replay_check` in `runner.py` |
| Eval store      | `tests/eval/eval_store.py`                                            |
| Security pytest | `tests/eval/test_security_audit.py`                                   |
| API contracts   | `tests/eval/test_api_contracts.py`                                    |
| E2E live        | `tests/eval/e2e/test_live_queries.py`, `e2e/conftest.py`              |
| Markers         | `pyproject.toml` `[tool.pytest.ini_options]`                          |
| Ignore artifacts | `.gitignore` (`golden_report.*`, `tests/eval/eval_runs/`)          |

## Findings

| Sev   | Finding | Evidence | Impact | Recommendation |
|-------|---------|----------|--------|----------------|
| **P0** | **Medium-tier retrieval goldens fail** when executed (empty `retrieved_context` vs keyword component checks). | `tests/eval/golden_set/cases/retrieval/q1_multi_hop_ai_act_gaps.yaml` (`retrieved_context: ""`); `run_retrieval_check` in `tests/eval/golden_set/runner.py`; local pytest `retrieval-q1` failed with missing components. | Nightly step “Golden set (all tiers, with eval store)” likely **fails**; **no signal** from those cases until fixed. | Populate `retrieved_context` with deterministic synthetic text **or** switch to `expect.replay` with committed fixtures **or** mark cases `slow`/`skip` until wired. |
| **P0** | **OpenAPI path expectations are stale** vs app (`/metrics`, `/telemetry`). | `api/routers/telemetry.py`; `tests/eval/test_security_audit.py` `test_documented_openapi_paths_match_expected_set`; `tests/eval/golden_set/cases/security/openapi_paths.yaml`; local failure on `security-openapi-paths`. | **PR CI** (`test_security_audit` + golden openapi case) **breaks** on current app shape. | Add `/metrics` and `/telemetry` to **both** the pytest `expected` set and the golden YAML `expected_paths`. |
| **P1** | **`requires_multi_hop` does not validate multi-hop**; it always sets `multi_hop_declared` to `True`. | `run_retrieval_check` in `tests/eval/golden_set/runner.py` (~lines 198–200). | **False confidence**: passing retrieval checks do **not** mean multi-hop retrieval occurred. | Implement a real check (e.g. trace metadata, fixture field) or remove/rename the flag until meaningful. |
| **P1** | **Nightly duplicates golden execution** and **overwrites** reports. | `nightly.yml` (golden step then full `pytest tests/eval/`); `golden_set/conftest.py` teardown writes `golden_report.json` / `.xml`. | Wasted minutes; **last writer wins** for reports; confusing artifacts. | Drop redundant step or exclude `golden_set` from the second pytest invocation. |
| **P2** | **CI job label “includes replay”** is inaccurate. | `.github/workflows/ci.yml`; no `replay:` in `tests/eval/golden_set/cases/`; `replay/.gitkeep` only. | Misleading operators/contributors. | Rename CI step or add a minimal replay golden once fixtures exist. |
| **P2** | **`slow` tier**: **no case uses `tier: slow`** in golden set. | `tests/eval/golden_set/manifest.yaml`; `TIER_ORDER` in `conftest.py`. | `--golden-tier=slow` is **effectively** “all tiers”; docs/job names may overstate “slow-only” behavior. | Add true `slow` cases or document that `slow` means “max tier cap,” not workload. |
| **P2** | **Nightly Python 3.12 only**; PR CI tests **3.12 + 3.13**. | `nightly.yml`; `ci.yml` matrix. | Rare version-specific regressions in eval **not** exercised nightly. | Add 3.13 to nightly **or** accept the gap. |
| **P2** | **`test_security_audit` references `docs/security_audit_report.md`** in an assertion message; file **not found** in repo. | `tests/eval/test_security_audit.py` | Doc/process drift only. | Add the doc or fix the message. |
| **P3** | **Eval store privacy**: golden path writes raw `case.input` to JSONL; no scrubbing. | `tests/eval/golden_set/report.py` `_write_eval_record`; `tests/eval/eval_store.py` `EvalRecord`; contrast `tests/eval/golden_set/recorder.py` `_scrub`. | Risk if YAML ever contains secrets or PII. | Document “no secrets in goldens”; optionally reuse scrub helper for eval store payloads. |
| **P3** | **Duplicate security logic**: golden `check_type` handlers mirror `tests/eval/test_security_audit.py`. | `tests/eval/golden_set/runner.py` `_check_*` vs `test_security_audit.py` | Maintenance burden; divergence risk (e.g. OpenAPI sets). | Single source of truth for expected path sets **or** call shared helper. |

## Failure-mode matrix

| Scenario | Symptom | Mitigation |
|----------|---------|------------|
| New routes without updating frozen OpenAPI sets | Golden `security-openapi-paths` + `test_documented_openapi_paths_match_expected_set` fail | Update both expectations together |
| Nightly golden includes medium retrieval with empty context | Retrieval lens fails | Fix YAML or use replay/fixtures |
| Misconfigured Chroma/Neo4j locally | App logs connection errors; E2E may still return 200 in placeholder mode | See `x-aria-mode` / `ARIA_PLACEHOLDER_API` in `tests/eval/e2e/test_live_queries.py` |
| `--emit-eval-store` with sensitive YAML | Secrets in `eval_runs/*.jsonl` | Gitignore (already), scrubbing, policy |
| Parallel pytest workers writing same JSONL | Possible interleaved/corrupt lines | Avoid xdist on eval store jobs or one file per worker |
| Wrong `API_KEY` during golden security checks | Handlers mutate `os.environ` | `runner.py` uses try/finally restore for `_check_api_key_enforcement` |

## Test gaps

- **Replay lens**: implemented (`run_replay_check`) but **unused**; no E2E-to-replay bridge in CI.
- **Retrieval goldens**: not run on PR CI (`fast` skips `medium`); when run, may **fail** without real context (see P0).
- **Python 3.13**: in PR matrix, **not** in nightly E2E.
- **Security marker**: `test_security_audit` sets `pytestmark = pytest.mark.security` but CI runs the file without `-m security` — marker unused for selective jobs.
- **`test_security_audit` vs golden security**: overlapping coverage; **drift** observed for OpenAPI.

## Recommended next steps (ordered)

1. **P0**: Extend OpenAPI expected sets to include `/metrics` and `/telemetry` in `test_security_audit.py` and `openapi_paths.yaml`; re-run fast goldens + security tests.
2. **P0**: Fix or quarantine **medium retrieval** goldens so `pytest … --golden-tier=slow` is green.
3. **P1**: Remove duplicate golden run from `nightly.yml` or narrow the second `pytest tests/eval/` invocation.
4. **P1**: Fix or document **`requires_multi_hop`** semantics in `run_retrieval_check`.
5. **P2**: Rename CI step text away from “replay” until replay cases exist; align eval docs with actual tier mapping.

## Verification note

Several items were **confirmed by local pytest** (OpenAPI drift, `retrieval-q1` failure). **GitHub Actions green/red status** was not verified in this audit run.

## Out of scope (related)

- `.github/workflows/security.yml` pip-audit job.
- SQLite WAL / `aria_telemetry.db-wal` from telemetry store (operational, not eval).
