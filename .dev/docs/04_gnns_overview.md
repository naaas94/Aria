# Graph Neural Networks: Overview and Relation to ARIA

## Concept definition

**Graph Neural Networks (GNNs)** are deep learning architectures that operate on **graph-structured inputs**. Unlike sequences (RNNs, Transformers on tokens) or grids (CNNs on images), GNNs respect **irregular topology**: arbitrary node degrees, permutation invariance of neighbor ordering (often), and edge-level features.

The unifying idea is **neural message passing**: each iteration, nodes **aggregate** information from neighbors, **transform** it with learned parameters, and **update** hidden representations. After one or more layers, node embeddings capture local (and, with depth, increasingly global) graph context.

Common baseline architectures:

### Graph Convolutional Network (GCN)

Kipf and Welling’s GCN simplifies convolution on graphs via **spectral** or **spatial** approximations. In the spatial view, a node’s new feature vector is a normalized sum (or mean) of neighbor features, followed by a linear map and nonlinearity. Depth stacks receptive fields; over-smoothing can occur if many layers are stacked without care.

**Inductive bias**: similar to averaging low-pass filters on signals — good for homophily (connected nodes resemble each other).

### Graph Attention Network (GAT)

GAT replaces fixed aggregation weights with **attention**: learned coefficients say how much each neighbor matters. Multiple **attention heads** capture different relationship motifs.

**Inductive bias**: adaptive neighbor weighting — useful when not all edges should contribute equally (heterophily-aware variants exist).

### GraphSAGE

GraphSAGE (**SAmple and aggreGatE**) focuses on **inductive** learning: sample a fixed number of neighbors per hop, aggregate (mean, LSTM, pool), then combine with the node’s own features. This scales to large graphs and supports **inference on unseen nodes** that were not present at training time, given their features and local graph.

**Inductive bias**: subsampling for scalability; emphasizes generalization beyond the training graph’s node set.

### Message passing (general form)

Most GNNs instantiate a message-passing neural network (MPNN) pattern:

1. **Message** — for each edge `(u → v)`, compute a message `m_uv = MSG(h_u, h_v, e_uv)` using sender, receiver, and edge features.
2. **Aggregate** — `AGG({ m_uv : u ∈ N(v) })` (sum, mean, max, attention-weighted sum).
3. **Update** — `h_v' = UPD(h_v, a_v)`.

Stacking layers increases the **receptive field** (roughly k-hop neighborhood after k layers), analogous to k-hop traversal in graph databases — but learned and continuous rather than symbolic.

## Why it matters

For **machine learning engineering (MLE)** roles, GNNs appear wherever data is inherently relational:

- Fraud detection (transaction graphs), recommendation (user–item–attribute graphs), knowledge graph completion, molecular property prediction, infrastructure dependency graphs, and social networks.

Skills that transfer:

- **Graph sampling and minibatching** for training at scale.
- **Handling heterogeneity** (multiple node/edge types) via relational GNNs or metapaths.
- **Evaluation pitfalls** — leakage across edges, transductive vs inductive splits, oversmoothing.

Even when production systems use **retrieval** rather than **end-to-end graph learning**, understanding GNNs clarifies *what embeddings of graphs mean* and how they differ from **text embeddings** of chunked documents.

## How it relates to ARIA (GraphRAG vs GNN)

ARIA’s retrieval stack (`aria/retrieval/`) combines **ChromaDB** dense retrieval over text chunks with **Neo4j** traversal for structured context (`GraphRetriever`, `HybridRetriever`). That approach is **GraphRAG**: symbolic graph + LLM + (optionally) vector search — **not** a trained GNN encoder.

### Similarities (intuition)

- Both care about **multi-hop context**: GNNs deepen receptive fields per layer; GraphRAG expands `expand_one_hop` / `expand_two_hops` from anchor nodes.
- Both exploit **topology**: who connects to whom matters, not only bag-of-words similarity.

### Differences (important for interviews and design reviews)

| Aspect | GNN (typical) | ARIA GraphRAG |
|--------|----------------|---------------|
| Representation | Learned continuous embeddings | Symbolic nodes/edges + Cypher |
| Training | Supervised / self-supervised on graph tasks | LLM + extraction + retrieval (no GNN loss in repo) |
| Generalization | Inductive models can embed new nodes with features | New data merged into Neo4j + re-embedded chunks |
| Explainability | Attention or gradients; often harder | Returned paths and labels are human-readable |
| Cost profile | GPU training, graph sampling | Graph DB + vector DB + LLM inference |

**Complementary**: one could imagine **future work** where a GNN encodes the compliance graph into vectors for link prediction (“likely missing `ADDRESSED_BY`”) or for hybrid retrieval features. ARIA as implemented does **not** include that layer; the documentation here positions GNNs as **adjacent science** rather than current dependency.

### Message passing vs Cypher expansion

- **Message passing** compresses neighborhood information into fixed-dimensional vectors through **differentiable** aggregation.
- **Cypher expansion** retrieves **explicit** neighbor records and paths for prompting — no shared global training step; the “aggregation” is **fusion** in `reranker.py` (heuristic score combination).

Understanding both helps MLEs choose: learn patterns from historical compliance graphs vs retrieve explicit regulatory structure for grounded generation.

### Transductive vs inductive learning

**Transductive** settings train (and often infer) on a **fixed** graph: all nodes exist at training time; the task may be semi-supervised node classification on the same vertex set. **Inductive** settings train on one graph (or subgraphs) and expect **new nodes** at test time with their own neighborhoods — GraphSAGE-style sampling was designed for this. Interviewers often probe whether you understand **leakage** when validation edges overlap training message paths; negative sampling and careful edge splits matter for link prediction.

### Oversmoothing and depth

Repeated message passing can make node representations **converge** toward similar vectors, erasing local distinctions — the **oversmoothing** problem. Mitigations include residual connections, jumping knowledge architectures, shallow networks with wider features, or decoupling depth from receptive field (e.g., personalized PageRank-style propagation). For compliance graphs with heterogeneous types, **heterophily** (connected nodes are *dissimilar*) can hurt standard GCN assumptions; specialized layers (GPR-GNN, H2GCN, etc.) exist but increase complexity.

### Heterogeneous graphs

Real graphs mix **types** of nodes and edges (ARIA’s schema is already heterogeneous: regulations, systems, teams). **Relational GCNs (R-GCN)** or **Heterogeneous Graph Transformer (HGT)**-style models assign type-specific transformations. Mapping ARIA’s `EdgeType` enum to learned relation embeddings would be the natural ML extension — still **not** implemented in this repository, but a credible roadmap item for link prediction or anomaly detection on obligations.

### What MLE interviews often emphasize

- **Problem formulation**: node-level vs graph-level prediction; link prediction negative sampling.
- **Scale**: neighbor sampling, subgraph minibatching, PyTorch Geometric / DGL familiarity.
- **Evaluation**: metrics per class for imbalanced obligations; temporal splits for evolving regulations.
- **Deployment**: training-serving skew; feature freshness when new systems onboard.

None of these replace GraphRAG for **grounded citation** to source text; they address **different products**: learned scoring vs auditable retrieval.

### Graph Transformers and long-range dependencies

Recent work treats graphs with **Transformer-style** attention over nodes or learned subgraphs, sometimes combined with structural encodings (Laplacian eigenvectors, random-walk positions). These models can capture **long-range** dependencies in fewer explicit hops than stacking many GNN layers, at the cost of quadratic attention over nodes (mitigated by sparsification or subgraph selection). For **very large** regulatory knowledge graphs, such architectures might summarize global structure; ARIA instead uses **community-less** GraphRAG indexing and explicit Cypher for local context, avoiding heavy graph-level training.

### Compliance-flavored GNN tasks (hypothetical)

If ARIA’s Neo4j graph were labeled with historical outcomes, one could formulate:

- **Node classification**: classify `Requirement` nodes by risk tier from past audits.
- **Link prediction**: suggest missing `ADDRESSED_BY` edges where policies likely exist but were not extracted.
- **Anomaly detection**: flag `InternalSystem` nodes with unusual obligation fan-in.

Each task needs **clean labels**, **temporal integrity**, and governance review before deployment. The current project scope emphasizes **retrieval and orchestration** rather than supervised graph learning.

## Tradeoffs

**GNN advantages**

- Can discover **latent** patterns (hidden risk clusters) when labels or objectives exist.
- Produces **dense features** for downstream classifiers end-to-end.

**GNN challenges**

- Data preparation (features per node, temporal graphs, label scarcity).
- Training infrastructure and debugging (oversmoothing, heterophily).
- Explainability requirements in regulated environments may favor symbolic retrieval.

**GraphRAG advantages (ARIA-style)**

- **Grounding** in auditable graph paths and source chunks.
- Faster to iterate with LLMs and extraction prompts without GPU graph training.

**GraphRAG challenges**

- Depends on **extraction quality** and schema discipline (`VALID_EDGES`, merge keys).
- Heuristic fusion may miss optimal ranking without learned rerankers.

## Further reading

- Kipf & Welling, *Semi-Supervised Classification with Graph Convolutional Networks* (ICLR 2017) — GCN.
- Veličković et al., *Graph Attention Networks* (ICLR 2018) — GAT.
- Hamilton, Ying, & Leskovec, *Inductive Representation Learning on Large Graphs* (NeurIPS 2017) — GraphSAGE.
- Gilmer et al., *Neural Message Passing for Quantum Chemistry* (ICML 2017) — MPNN framing.
- Bronstein et al., *Geometric Deep Learning: Grids, Groups, Graphs, Geodesics, and Gauges* — unified perspective.
- Microsoft GraphRAG publication (local-to-global) — contrast with differentiable graph encoders; see `docs/03_graphrag_vs_vector_rag.md` for ARIA’s retrieval mapping.

---

*ARIA: Automated Regulatory Impact Agent — symbolic property graphs and hybrid retrieval; GNNs discussed as conceptual adjacent for MLE readers.*
