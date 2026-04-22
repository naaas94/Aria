# Knowledge Graphs in ARIA

## Concept definition

A **knowledge graph** is a structured representation of entities and the relationships among them. Unlike a single table or document collection, a graph makes **connections** first-class: you query by pattern, path length, and topology, not only by filtering rows.

Two dominant data models appear in industry and research:

### Property graphs (labeled property graph, LPG)

In an LPG, data lives in **nodes** and **directed edges** (relationships). Each node has one or more **labels** (similar to types or classes) and a bag of **properties** (key-value pairs). Relationships are also typed and may carry properties (for example `since`, `confidence`, `source_span`). Neo4j is the canonical commercial open ecosystem for this model; its query language is **Cypher**.

Core primitives:

- **Node**: represents an entity; identified internally by an internal graph id, and in ARIA by a stable domain `id` property used for merges.
- **Edge (relationship)**: a directed link from a source node to a target node, with a relationship type in upper case by convention in this project (`CONTAINS`, `IMPOSES`, …).
- **Property**: scalar or simple structured data attached to a node or relationship.

### RDF graphs

The **Resource Description Framework (RDF)** expresses knowledge as a set of **triples**: `(subject, predicate, object)`. Subjects and objects are often IRIs; predicates typically come from shared vocabularies. **SPARQL** is the W3C query language. Triple stores emphasize standards-based interchange, ontology languages (OWL), and sometimes **description logic** reasoning.

LPG and RDF can represent similar domains, but the *default ergonomics* differ: property graphs emphasize traversal and application-centric modeling; RDF emphasizes global identity of resources and semantic interoperability.

### When graphs tend to beat relational databases

Relational models excel at **ACID transactions**, **set-based analytics** over stable schemas, and decades of operational patterns. Graphs tend to be preferable when:

1. **Questions are inherently navigational** — for example, “starting from this regulation, find requirements that affect customer-facing systems but are not addressed by any internal policy.” Such queries map to multi-hop patterns; in SQL they become chains of joins or recursive CTEs that are harder to read and tune.

2. **The schema is semistructured or evolving** — regulatory corpora gain new cross-references, amendment chains, and entity types. Adding a new relationship type in a graph is often a matter of writing new edges; in a normalized schema it may require new tables or polymorphic patterns.

3. **Entity resolution and deduplication** are central — the same system or team may be mentioned across documents; a graph supports `MERGE` on stable keys and shared nodes rather than duplicating foreign keys everywhere.

4. **Explainability of paths** matters for compliance — returning not only “an answer” but *why* (which articles, which requirements, which ownership edges) supports audit trails.

Graphs are not a replacement for warehouses or OLTP databases; they are a **specialized layer** for connected domain logic. ARIA uses a graph alongside **vector search** (ChromaDB) and orchestration so that semantic similarity and structural truth can be combined.

## Why it matters

Regulatory compliance is a **network phenomenon**: instruments amend and reference one another; articles impose obligations; obligations land on systems; systems and policies have organizational owners; deadlines attach to specific articles. Text-only retrieval can surface *similar paragraphs* but may lose **which obligation applies to which system under which policy**.

By storing ARIA’s domain as a Neo4j property graph, the system can:

- Run **explicit traversals** (multi-hop Cypher) that mirror compliance questions.
- Provide **structured context** to LLMs after vector anchoring (see `03_graphrag_vs_vector_rag.md`).
- Enforce **integrity** via uniqueness constraints on merge keys and an allow-listed query surface.

The **Automated Regulatory Impact Agent (ARIA)** therefore treats the graph as the authoritative structure for regulatory and organizational linkage, while unstructured text remains chunked and embedded for semantic recall.

## How it is implemented in this repo

### Schema and contracts

Node and relationship vocabulary is defined in `aria/contracts/graph_entities.py`:

- `NodeLabel` includes `Regulation`, `Article`, `Requirement`, `PolicyDocument`, `InternalSystem`, `Team`, `Jurisdiction`, and `Deadline`.
- `EdgeType` includes `CONTAINS`, `IMPOSES`, `AMENDS`, `REFERENCES`, `APPLIES_IN`, `AFFECTS`, `ADDRESSED_BY`, `OWNED_BY`, and `HAS_DEADLINE`.

`GraphNode` and `GraphEdge` pydantic models describe payloads for writes and MCP typing; each node’s properties must include `id` as the merge key (`merge_key` property).

`aria/graph/schema.py` ties labels to merge keys (`NODE_MERGE_KEYS`: all use `id`), lists **valid** `(source_label, edge_type, target_label)` triples in `VALID_EDGES`, and generates:

- `CREATE CONSTRAINT … REQUIRE n.id IS UNIQUE` per label.
- Secondary **indexes** on common filter properties (`title`, `number`, `obligation_type`, `category`, `name`).

This keeps the graph **consistent** with the domain contract and speeds typical regulatory lookups.

### Cypher and the query library

**Cypher** is Neo4j’s declarative pattern-matching language. Patterns use ASCII art–like syntax, for example:

```cypher
MATCH (r:Regulation {id: $regulation_id})-[:CONTAINS]->(a:Article)
RETURN a ORDER BY a.number
```

ARIA does **not** pass user-supplied Cypher to the database. Instead, `aria/graph/queries.py` registers named `CypherQuery` objects with fixed `cypher` strings and explicit `parameter_names`. The `GraphRetriever` and MCP tools call `execute_named_query` to bind parameters safely.

Illustrative categories in the library:

- **Regulation-centric reads** — fetch a regulation, list its articles.
- **Multi-hop compliance** — patterns such as “requirements affecting systems, owned by teams, lacking `ADDRESSED_BY` to a policy” (`uncovered_requirements`).
- **GraphRAG neighborhood expansion** — `expand_from_node`, `expand_two_hops` for retrieval anchors.
- **Cross-regulation linkage** — `connected_regulations` over `AMENDS` and `REFERENCES`.

### Retrieval integration

`aria/retrieval/graph_retriever.py` defines `GraphRetriever`, which uses `Neo4jClient` to run those named queries. Results are wrapped in `GraphContext` with `neighbors` or `paths` and a `context_text` serializer for LLM prompts. This connects the **property graph** directly to the hybrid retrieval pipeline.

### Ingestion alignment

`aria/ingestion/pipeline.py` orchestrates parse → chunk → (optional) entity extraction → graph write → vector index. Extracted entities are written through a `graph_writer` that consumes structured extraction output compatible with `GraphWritePayload`. Thus the **same domain IDs** can appear in Chroma metadata (for anchoring) and Neo4j (for traversal).

### Neo4j label–property model in practice

Neo4j stores nodes and relationships as **records** in a native graph engine. Labels are lightweight type markers (a node may have multiple labels, though ARIA uses one primary label per entity type in contracts). Properties are stored as maps; relationship types are strings. The query planner chooses **label scans**, **index seeks**, and **expand** operators based on predicates such as `{id: $x}` and patterns like `-[:CONTAINS]->`.

**MERGE** (used conceptually alongside uniqueness constraints) is the idempotent upsert primitive: match on key properties or create if absent. **CREATE** always inserts new graph elements. Production ingestion favors MERGE on `id` so re-running pipelines does not duplicate regulations or requirements. Constraints declared in `generate_constraint_statements()` back that discipline at the database level.

### Representative Cypher from ARIA’s query library

GraphRAG expansion in `aria/graph/queries.py` uses parameterized patterns so anchors are not ambiguous across labels:

```cypher
MATCH (n {id: $node_id})
WHERE $node_label IN labels(n)
OPTIONAL MATCH (n)-[r]-(neighbor)
RETURN n, type(r) AS rel_type, neighbor
LIMIT $limit
```

Two-hop expansion returns bounded variable-length paths:

```cypher
MATCH (n {id: $node_id})
WHERE $node_label IN labels(n)
OPTIONAL MATCH path = (n)-[*1..2]-(neighbor)
RETURN nodes(path) AS nodes, relationships(path) AS rels
LIMIT $limit
```

Cross-regulation discovery uses **alternation** on relationship types and a bounded depth:

```cypher
MATCH (r:Regulation {id: $regulation_id})
-[:AMENDS|REFERENCES*1..2]-(related:Regulation)
RETURN DISTINCT related.id AS id, related.title AS title, ...
```

These examples illustrate how **Cypher** expresses both **local neighborhoods** (for LLM context) and **domain-specific analytics** (amendment/reference networks) on the same property graph.

### RDF vs LPG (summary comparison)

| Dimension | RDF / triple stores | LPG / Neo4j (ARIA) |
|-----------|---------------------|---------------------|
| Atomic fact | Triple | Node, relationship, or property entry |
| Identity | Global IRIs | Application-scoped `id` property + internal graph id |
| Query language | SPARQL | Cypher |
| Reasoning | OWL, RDFS entailment (optional) | Application rules + Cypher (no DL engine in ARIA) |
| Typical sweet spot | Linked open data, ontology-heavy publishing | Application graphs, traversal-heavy APIs |

## Tradeoffs

**Property graph vs RDF**

- LPG + Cypher prioritizes developer velocity for application graphs and tight integration with Neo4j features (constraints, indexes, APOC). Publishing as five-star linked data requires mapping layers.
- RDF + SPARQL maximizes vocabulary reuse and federated queries across public datasets; operational graph-RAG stacks are less standardized than Neo4j-centric ones.

**Graph vs purely relational**

- Recursive compliance patterns are clearer in Cypher; reporting across the enterprise may still be exported to SQL/BI tools.
- Deep graphs with supernodes (hubs) need careful indexing and query limits; ARIA uses `limit` parameters on expansion queries.

**Strict schema vs ontology reasoning**

- ARIA enforces allowed edges in code (`VALID_EDGES`) rather than OWL inference: predictable behavior for agents, but no automatic subproperty entailment.

**Allow-listed queries only**

- Security and auditability improve; exploratory analysis in production still belongs in controlled tooling or additional read-only named queries.

## Further reading

- Ian Robinson, Jim Webber, and Emil Eifrem, *Graph Databases* (O’Reilly) — modeling mindset and traversal patterns.
- Angles & Gutierrez, “An Introduction to Graph Data Management” — survey of graph models including RDF and property graphs.
- [Neo4j Graph Data Modeling](https://neo4j.com/docs/getting-started/graph-database/) — official introduction to LPG concepts.
- [Cypher Manual](https://neo4j.com/docs/cypher-manual/current/) — syntax, constraints, query tuning.
- [RDF 1.1 Concepts and Abstract Syntax](https://www.w3.org/TR/rdf11-concepts/) — triple model and RDF graphs.
- [SPARQL 1.1 Query Language](https://www.w3.org/TR/sparql11-query/) — if comparing graph query paradigms.
- Edge et al., *From Local to Global: A Graph RAG Approach to Query-Focused Summarization* — research context for graph-augmented retrieval (see also `docs/03_graphrag_vs_vector_rag.md`).

---

*ARIA: Automated Regulatory Impact Agent — Neo4j, ChromaDB, GraphRAG, multi-agent orchestration, MCP, and A2A protocols.*
