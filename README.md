# ARIA — Automated Regulatory Impact Agent

GraphRAG-powered multi-agent system for regulatory compliance analysis. Ingests regulatory documents, builds a Neo4j knowledge graph, answers multi-hop compliance queries, and routes remediation tasks through a stateful orchestration layer.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Regulatory  │────▶│  Ingestion   │────▶│  Knowledge   │
│  Documents   │     │  Pipeline    │     │  Graph (Neo4j)│
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                 │
                     ┌──────────────┐     ┌──────▼───────┐
                     │  ChromaDB    │◀───▶│   GraphRAG   │
                     │  Vectors     │     │  Retrieval   │
                     └──────────────┘     └──────┬───────┘
                                                 │
                     ┌──────────────┐     ┌──────▼───────┐
                     │   FastAPI    │◀────│  Multi-Agent  │
                     │   Interface  │     │  Orchestrator │
                     └──────────────┘     └──────────────┘
```

## Quickstart

```bash
# 1. Clone and install
git clone <repo-url> && cd aria
pip install -e ".[dev]"

# 2. Copy environment template
cp .env.example .env

# 3. Start infrastructure
docker compose up -d neo4j chromadb

# 4. Seed sample data
python scripts/seed_graph.py

# 5. Run the API
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload

# 6. Run tests
pytest
```

## Key Concepts

| Concept | Location | Documentation |
|---------|----------|---------------|
| Knowledge Graph | `aria/graph/` | `docs/01_knowledge_graphs.md` |
| GraphRAG | `aria/retrieval/` | `docs/03_graphrag_vs_vector_rag.md` |
| Scratch Orchestration | `aria/orchestration/scratch/` | `docs/08_stateful_graphs_from_scratch.md` |
| MCP Protocol | `aria/protocols/mcp/` | `docs/05_mcp_protocol.md` |
| A2A Protocol | `aria/protocols/a2a/` | `docs/06_a2a_protocol.md` |
| LangGraph Reference | `aria/orchestration/langgraph_reference/` | `docs/09_langgraph_reference.md` |

## Tech Stack

- **Graph DB**: Neo4j 5 (local Docker)
- **Vector Store**: ChromaDB
- **LLM**: Ollama + LiteLLM abstraction
- **Orchestration**: Custom stateful graph + LangGraph reference
- **Protocols**: MCP (tool access) + A2A (agent delegation)
- **API**: FastAPI
- **Contracts**: Pydantic v2
