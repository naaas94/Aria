# GraphRAG vs Vector RAG in ARIA

## Concept definition

**Vector RAG** (retrieval-augmented generation with dense retrieval) typically:

1. **Chunks** documents into segments.
2. **Embeds** each chunk into a vector space.
3. At query time, **embeds the question** and retrieves the **nearest neighbors** by cosine or dot-product similarity in a vector database (here, **ChromaDB**).
4. Concatenates retrieved text into the LLM context.

Strengths: semantic fuzziness (“this obligation sounds like reporting”) and scalability on flat corpora.

**Limitations of vector-only RAG** (especially for compliance):

- **Lost relational context** — chunks that mention a requirement and a system may not co-occur in the same segment; similarity may retrieve one without the other.
- **No guaranteed multi-hop reasoning** — “regulation → article → requirement → system → team” is a *path* in data, not a single embedding direction.
- **Duplicate and contradictory snippets** — similar language across articles does not imply legal dependency; vectors conflate wording, not amendment graphs.

**GraphRAG** (in the broad research sense, notably Microsoft’s “local-to-global” pipeline) augments or replaces flat retrieval with **graph structure**:

### Indexing phase (conceptual full pipeline)

1. **Entity and relationship extraction** from source text (LLM or NLP).
2. **Graph population** — nodes and edges materialized in a graph store.
3. **Community detection** — cluster densely connected regions; summarize each community for high-level retrieval.
4. **Embedding** — embed text summaries, community reports, and/or original chunks for hybrid search.

Not every production system implements all steps; some use **lightweight GraphRAG**: structured graph for traversal + vectors for anchoring only.

### Query phase (conceptual)

1. **Embed** the user query (and optionally classify intent).
2. **Anchor** — find starting nodes or chunks (vector search, keyword, or entity linking).
3. **Expand** — traverse k hops in the graph to gather structured neighborhood evidence.
4. **Fuse** — merge ranked evidence from vector and graph sources for the LLM (re-ranking, deduplication, budgeting tokens).

ARIA implements a **practical subset**: structured Neo4j graph + Chroma chunk embeddings, **without** automated community detection in the indexing path. The following sections map concepts to code honestly.

## Why it matters

Regulatory questions are often **structural**: impact on systems, coverage by policies, deadlines attached to articles, cross-references between instruments. Pure similarity may return **plausible prose** that misses **obligatory linkage**.

Combining vectors and graphs gives:

- **Recall** from semantics (vector search over chunks).
- **Precision and explainability** from traversals (named Cypher patterns with explicit relationships).

For a portfolio narrative, ARIA demonstrates that split: **ChromaDB** for “what text is similar?” and **Neo4j** for “what is legally and operationally connected?”.

## How it is implemented in this repo

### Vector store: `aria/retrieval/vector_store.py`

`VectorStore` wraps **ChromaDB** (`HttpClient`, configurable host/port via `CHROMA_HOST`, `CHROMA_PORT`). The collection defaults to `aria_regulatory_chunks` with cosine space metadata (`hnsw:space`).

- `connect()` obtains or creates the collection.
- `index_chunks(chunks)` **upserts** by `chunk_id`, storing document text and metadata (including `source_hash` from `DocumentChunk` and arbitrary chunk metadata).
- `search(query_text, top_k, where)` runs similarity search and returns `RetrievedChunk` objects with `chunk_id`, `text`, `score` (derived from distance), and `metadata`.

This layer is **pure vector RAG** capability: no graph awareness in the query itself.

### Graph retrieval: `aria/retrieval/graph_retriever.py`

`GraphRetriever` executes **parameterized, named Cypher** via `execute_named_query` and `Neo4jClient`:

- `expand_one_hop` — neighborhood for a single anchor (`expand_from_node` query).
- `expand_two_hops` — deeper paths (`expand_two_hops`).
- `get_regulation_impact`, `get_uncovered_requirements`, `get_connected_regulations` — domain-specific multi-hop analytics.

Results become `GraphContext` objects with `neighbors` or `paths`, serialized to `context_text` for LLM prompts.

This layer is **graph-only** retrieval: no embedding of the user query inside the graph retriever itself.

### Hybrid query phase: `aria/retrieval/hybrid_retriever.py`

`HybridRetriever.retrieve` implements the **embed → anchor → expand → fuse** pattern as follows:

1. **Embed / search (implicit)** — Chroma performs embedding internally when `VectorStore.search` is called with `query_text`.
2. **Anchor** — top vector hits supply anchor candidates. For each of the **first five** chunks (`vector_chunks[:5]`), the retriever reads `node_id` from metadata, falling back to `chunk_id` if absent.
3. **Expand** — for each anchor, `GraphRetriever.expand_one_hop` or `expand_two_hops` is used depending on `graph_hops` (constructor default 1). Failures are logged and skipped so vector results still return.
4. **Fuse** — `rerank_results` (see below) merges vector scores with graph presence.

`HybridResult` exposes `context_text` (preferring reranked output) and `trace` for evaluation (counts and score lists). This matches the module docstring: vector finds anchors, graph adds structure, fusion prepares ranked context.

### Fusion / reranking: `aria/retrieval/reranker.py`

`rerank_results` implements a **transparent scoring policy**:

- Base score = vector similarity.
- **Boost** (`GRAPH_BOOST = 0.15`) if the chunk id appears in graph neighborhoods (anchor or extracted neighbor ids).
- Graph-only anchors not in vector results can appear with a fixed base (0.5) plus boost.
- Results filter below `MIN_SCORE_THRESHOLD` and cap at `max_results`.

This is **not** a learned cross-encoder; it is an interpretable heuristic suitable for demos and ablations.

### Indexing alignment: `aria/ingestion/pipeline.py`

Ingestion order: parse → `chunk_text` → optional **entity extraction** → optional **graph_writer(entities)** → optional **vector_indexer(chunks)**.

So ARIA’s **indexing** includes:

- Entity extraction → graph population (when wired).
- Chunk embedding → Chroma upsert.

There is **no** implemented pipeline stage in this repository for **Leiden-style community detection** or **community summary embedding** as in the full Microsoft GraphRAG paper. Those remain **conceptual extensions** documented here for comparison and portfolio discussion.

### API and evaluation hooks

- `api/routers/query.py` exposes a flag for GraphRAG (hybrid) vs vector-only retrieval.
- `tests/eval/graphrag_vs_vector_rag.py` and `scripts/benchmark_retrieval.py` support side-by-side comparison narratives.

### Configuration knobs (`HybridRetriever`)

Constructor parameters in `aria/retrieval/hybrid_retriever.py` control cost and depth:

- `vector_top_k` — breadth of semantic recall from Chroma (default 10).
- `graph_hops` — 1 uses `expand_one_hop`; 2 uses `expand_two_hops` (default 1).
- `graph_limit` — caps rows returned per expansion query (default 25).

Per-call overrides exist for `vector_top_k` and `graph_hops`; `node_label_hint` defaults to `"Article"` because chunks often anchor to article-level nodes. Misalignment between actual chunk metadata and this hint can reduce match quality in `WHERE $node_label IN labels(n)`.

### End-to-end retrieval narrative

For a single user query, the hybrid path conceptually executes:

1. `VectorStore.search` embeds the query (inside Chroma) and returns ranked `RetrievedChunk` rows.
2. For up to five high-scoring chunks, extract anchor `node_id` (or `chunk_id`).
3. For each anchor, run Neo4j read queries via `GraphRetriever`, collecting `GraphContext` instances.
4. `rerank_results` merges identifiers seen in vector hits and graph neighborhoods, applies boosts, sorts, and truncates.

The final `HybridResult.context_text` prefers the reranked narrative; if reranking yields nothing, it falls back to separate vector and graph sections (see `HybridResult.context_text` implementation).

### Failure modes and mitigations

- **Missing `node_id` in metadata** — expansion may use `chunk_id`, which might not exist as a graph node `id`; graph expansion can return empty context silently after logging.
- **Extraction drift** — invalid edges rejected by writers still leave text in Chroma; vectors may retrieve text disconnected from the graph.
- **Hub nodes** — highly connected articles can dominate one-hop results; `limit` mitigates but does not prioritize neighbors by type.

These issues are common to hybrid systems and motivate evaluation scripts in `tests/eval/` rather than assuming correctness from architecture alone.

## Tradeoffs

**Vector-only**

- Simpler operations, fewer moving parts; weak on explicit multi-hop obligations unless chunks duplicate structure.

**Full GraphRAG (paper-style)**

- Rich global summaries via communities; higher indexing cost, more LLM calls, tuning complexity.

**ARIA hybrid (implemented)**

- Good demonstration of **anchor + expand + fuse** with Neo4j + Chroma.
- Depends on **metadata alignment** (`node_id` in chunks); missing links degrade graph expansion.
- Top-5 anchoring limits graph cost but may miss relevant distant nodes.
- Reranker is heuristic; production might add cross-encoders or learning-to-rank.

**Community detection omitted**

- Faster indexing and smaller codebase; less “global summarization” at graph scale.

## Further reading

- Edge et al., *From Local to Global: A Graph RAG Approach to Query-Focused Summarization* — canonical GraphRAG indexing and query phases.
- Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks* — RAG foundations.
- `aria/retrieval/vector_store.py`, `graph_retriever.py`, `hybrid_retriever.py`, `reranker.py` — ARIA implementation paths.
- Neo4j Graph Data Science documentation — community detection algorithms if extending ARIA’s indexing phase.

---

*ARIA: Automated Regulatory Impact Agent — ChromaDB vector search, Neo4j graph traversal, hybrid GraphRAG retrieval.*
