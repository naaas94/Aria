# T6 — Golden path wet run (mvp-phase1-golden-wet-run)

**Date:** 2026-05-30  
**Tier:** architectural  
**Executor:** T6 packet

## Chosen approach

Executed the full Phase 1 command sequence on a live stack (`ARIA_PLACEHOLDER_API=false`): `docker compose up -d neo4j chromadb`, then `aria init` → `aria ingest tests/fixtures/sample_regulation.html` → `aria query` → `aria impact reg-gdpr` → `aria telemetry --hours 1` → `aria serve` + `curl /ready` → preflight vs readiness checks → `pytest tests/integration -m integration`. Recorded results in `.dev/MVP_PICKUP.md` wet run log.

Live LLM used **OpenAI `gpt-4o-mini`** with `LLM_BASE_URL=https://api.openai.com/v1` because local Ollama did not satisfy the 12s `probe_llm_reachable` budget (missing `llama3.2` tag; other models timed out on cold start).

## Alternatives rejected

| Alternative | Reason |
|-------------|--------|
| `ARIA_PLACEHOLDER_API=true` for golden path | Bypasses live stack; violates Phase 1 contract. |
| `scripts/seed_corpus.py` as ingest | Skips full wiring; leaves query/impact ungrounded (Flag 4). |
| Halt on Chroma `unhealthy` in compose | v2 heartbeat and `aria status` chroma checks passed; functional blocker not proven. |
| `scripts/seed_graph.py` for impact ID | Not needed; T4 `regulation_ids` line listed `reg-gdpr` after live ingest. |

## Assumptions made

- Neo4j/Chroma defaults (`bolt://localhost:7687`, `localhost:8000`) match docker-compose port mapping.
- Operator may use cloud LLM when Ollama model tags in `.env.example` are absent or slow.
- Integration tests remain placeholder-mode (`ARIA_PLACEHOLDER_API=true`) even when the wet run exercises live mode.

## Preflight vs readiness (evidence)

| Check | Result |
|-------|--------|
| `aria ingest` with bad LLM | Exit **1**, `missing: llm: ...` |
| `aria status` with same env | Exit **0**, `llm fail` + T5 note |
| `GET /ready` with bad LLM | HTTP **200**, `"llm": false`, `"errors": {"llm": "..."}` |
| `aria ingest` with good LLM | Exit **0**, full pipeline success |

Conclusion: ingest preflight requires Neo4j + Chroma + LLM; `/ready` stays **200** when only LLM fails.

## Step results (summary)

| Step | Exit | Notes |
|------|------|-------|
| docker compose | 0 | neo4j healthy; chroma compose health flaky |
| aria status | 0 | All deps ok with OpenAI config |
| aria init | 0 | |
| aria ingest | 0 | `regulation_ids` printed (T4) |
| aria query | 0 | Retrieval grounded |
| aria impact | 0 | 0 requirements (graph topology gap) |
| aria telemetry | 0 | |
| aria serve + /ready | 200 | Port 8080 (T3) |
| pytest integration | 0 | 25/25 with placeholder env |

## Items deferred

- **Chroma compose healthcheck:** image may lack `curl` or should target `/api/v2/heartbeat` — fix in infra subtask, not T6.
- **`.env.example` Ollama model tag:** align with commonly installed tags or document warm-up / timeout expectations.
- **Impact chain after ingest-only sample:** populate `AFFECTS` / `ADDRESSED_BY` or seed internal systems in a follow-on data task.
- **Flag 6 comprehensive CliRunner suites:** out of Phase 1 scope per plan.
- **Automated wet-run replay script:** manual session log at `.dev/wet-run-t6-session.log` (local only, not committed).
