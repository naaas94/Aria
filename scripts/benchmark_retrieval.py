"""Runs retrieval benchmarks and prints results.

Compares vector-only vs GraphRAG retrieval on the standard eval
question set, printing a formatted comparison table.

Run: python scripts/benchmark_retrieval.py
"""

from __future__ import annotations

from tests.eval.graphrag_vs_vector_rag import (
    EVAL_QUESTIONS,
    print_comparison_table,
    score_retrieval,
    RetrievalScore,
)


def run_benchmark() -> None:
    """Run the retrieval benchmark with simulated contexts."""

    vector_context = (
        "The GDPR regulation requires data protection impact assessments. "
        "Article 35 specifies that controllers shall carry out an assessment. "
        "Personal data must be processed lawfully and transparently. "
        "The right to erasure allows data subjects to request deletion."
    )

    graphrag_context = (
        "The GDPR regulation requires data protection impact assessments. "
        "Article 35 specifies that controllers shall carry out an assessment. "
        "The CRM system processes personal data and is owned by Engineering team. "
        "ML Risk Scoring system handles financial data, owned by Data Science team. "
        "The requirement affects the HR Platform which has a gap — no policy covers it. "
        "The EU AI Act references GDPR and imposes transparency obligations. "
        "Article 52 requires disclosure when users interact with AI systems. "
        "The Customer Chatbot system is affected and must comply by 2025-08-01. "
        "Legal & Compliance team owns the Data Privacy Policy (version 3.1). "
        "Human Resources team has no addressing policy for employee data processing."
    )

    scores: list[RetrievalScore] = []

    for q in EVAL_QUESTIONS:
        scores.append(score_retrieval(q, vector_context, "vector"))
        scores.append(score_retrieval(q, graphrag_context, "graphrag"))

    print_comparison_table(scores)

    vector_avg = sum(
        s.completeness for s in scores if s.strategy == "vector"
    ) / len(EVAL_QUESTIONS)
    graphrag_avg = sum(
        s.completeness for s in scores if s.strategy == "graphrag"
    ) / len(EVAL_QUESTIONS)

    print(f"\nVector RAG average completeness: {vector_avg:.1%}")
    print(f"GraphRAG average completeness:  {graphrag_avg:.1%}")
    print(f"GraphRAG improvement:           {graphrag_avg - vector_avg:+.1%}")


if __name__ == "__main__":
    run_benchmark()
