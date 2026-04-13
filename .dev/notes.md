- Duplication tax: LangGraph nodes importing from scratch is DRY-friendly, but you still have two graphs and two state representations (ARIAState vs ARIAStateDict). Any behavior change in routing or nodes needs discipline to keep parity — fine for research, ongoing cost for a growing team.



--- 


- Process-level state: _ingested_hashes in the ingestion pipeline is documented as in-process only; that’s correct, but in multi-worker Uvicorn or horizontal scale it’s easy to forget. Neo4j-backed dedup helps; the global set is still a footgun for “why did this doc ingest twice?” [for prod notes?]

- Exception handling in main.py: The catch-all handler special-cases HTTPException and RequestValidationError inside the generic Exception handler. FastAPI normally routes those to dedicated handlers first; the extra branches are either defensive redundancy or a sign something was confusing during debugging. Not wrong, just worth a quick sanity check that ordering is intentional.


- Naming and mental load: scratch as the real engine name is candid but reads “throwaway” to newcomers. If it’s the canonical runtime, eventually renaming (or a one-line package docstring at aria/orchestration/__init__.py) would reduce “is this production?” anxiety.

