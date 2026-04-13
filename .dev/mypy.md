- reamining: 
        Step 5: Burn down test annotations in slices
        Once CI is green with the relaxed test override, tackle tests in batches by folder:

        tests/unit/ — smallest, most self-contained, annotate -> None on all test methods
        tests/eval/ — fixtures and helpers may need dict[str, Any] or concrete types
        tests/integration/ — often the trickiest due to async fixtures and mocks
        For each batch: remove that module from the disallow_untyped_defs = false override, fix the errors, PR it.

    Remaining test-tree mypy debt (not blocking CI)
    Running bare mypy (which includes tests via files) shows 66 errors across 17 test files. None of these block CI since CI runs mypy aria api. The main categories for future cleanup:

    Category	Count	Example files
    Bare dict (missing type params)
    ~15
    test_orchestration.py, test_trajectory_eval.py, test_safety_reliability.py
    no-any-return
    ~5
    loader.py, runner.py, conftest.py, test_middleware_telemetry.py
    attr-defined (re-exports)
    ~5
    api_requests.py, test_live_queries.py, test_api_contracts.py
    arg-type (test fakes vs Protocol)
    ~5
    test_health_assessment.py, test_api_contracts.py
    unused-ignore (stale suppressions)
    ~5
    test_security_audit.py, test_edge_cases.py, conftest.py
    Generator return types (misc)
    ~4
    conftest.py, test_llm_telemetry.py
    Dict item type mismatches
    ~10
    test_api_contracts.py

## Context: 

You’re dealing with two separate problems. Fix them in order: make mypy runnable and scoped, then burn down errors in slices.


2. The 270 errors: don’t fix “everything” in one PR
With strict = true, most noise is tests (no-untyped-def, missing -> None on test methods, bare dict) plus a smaller set of real issues in aria/ and api/.

Sustainable approach:

Tests second, in batches
Either:

Add return types to test functions (-> None), annotate fixtures/helpers, replace bare dict with dict[str, Any] or concrete types; or
Add a [[tool.mypy.overrides]] for tests.* with slightly relaxed options (e.g. disallow_untyped_defs = false) only if you want CI green quickly while you incrementally annotate tests.
Touch the ingestion line only where mypy already complained
For example, test_safety_reliability.py line ~150: annotate the vector indexer as taking list[DocumentChunk]. That’s aligned with your new VectorIndexerFn and clears no-untyped-def there.

