"""Side-by-side retrieval quality comparison: GraphRAG vs pure vector RAG.

Defines a fixed set of multi-hop compliance questions with expected
answer components, then scores both retrieval strategies on
completeness and factual correctness.

Run: pytest tests/eval/graphrag_vs_vector_rag.py -v --tb=short -m eval
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest


@dataclass
class EvalQuestion:
    """A single evaluation question with expected answer components."""

    id: str
    question: str
    expected_components: list[str] = field(default_factory=list)
    requires_multi_hop: bool = True
    description: str = ""


EVAL_QUESTIONS = [
    EvalQuestion(
        id="q1",
        question="Which EU AI Act requirements affect our systems and have no existing policy coverage?",
        expected_components=["system_name", "requirement_text", "team_name", "gap_status"],
        requires_multi_hop=True,
        description="Requires regulation -> article -> requirement -> system -> team traversal with policy gap check",
    ),
    EvalQuestion(
        id="q2",
        question="What are all the compliance deadlines for the EU AI Act and which teams are responsible?",
        expected_components=["deadline_date", "article_number", "team_name"],
        requires_multi_hop=True,
        description="Requires regulation -> article -> deadline + requirement -> system -> team",
    ),
    EvalQuestion(
        id="q3",
        question="Which teams are affected by both GDPR and EU AI Act requirements?",
        expected_components=["team_name", "regulation_title"],
        requires_multi_hop=True,
        description="Cross-regulation multi-hop: two regulation trees joined via team ownership",
    ),
    EvalQuestion(
        id="q4",
        question="What is the right to erasure under GDPR?",
        expected_components=["article_text"],
        requires_multi_hop=False,
        description="Single-hop factual question — vector RAG should handle this well",
    ),
    EvalQuestion(
        id="q5",
        question="List all systems processing personal data and the regulatory requirements that apply to them",
        expected_components=["system_name", "data_types", "requirement_text", "regulation_title"],
        requires_multi_hop=True,
        description="Data-type driven traversal: system -> data_types -> matching requirements -> regulations",
    ),
]


@dataclass
class RetrievalScore:
    question_id: str
    strategy: str  # "vector" or "graphrag"
    component_hits: dict[str, bool] = field(default_factory=dict)

    @property
    def completeness(self) -> float:
        if not self.component_hits:
            return 0.0
        return sum(self.component_hits.values()) / len(self.component_hits)


def score_retrieval(
    question: EvalQuestion,
    retrieved_context: str,
    strategy: str,
) -> RetrievalScore:
    """Score a retrieval result against expected components.

    This is a simplified lexical check — production evaluation would
    use LLM-as-judge or human annotation.
    """
    hits: dict[str, bool] = {}
    context_lower = retrieved_context.lower()

    component_keywords = {
        "system_name": ["crm", "ml risk", "hr platform", "chatbot"],
        "requirement_text": ["shall", "must", "require", "obligation"],
        "team_name": ["engineering", "legal", "data science", "human resources"],
        "gap_status": ["gap", "uncovered", "no policy", "not addressed"],
        "deadline_date": ["2025", "2026", "deadline"],
        "article_number": ["article 5", "article 6", "article 9", "article 17", "article 35", "article 52"],
        "regulation_title": ["gdpr", "ai act", "data protection", "artificial intelligence"],
        "article_text": ["erasure", "right to be forgotten", "personal data"],
        "data_types": ["personal_data", "financial_data", "biometric", "employee"],
    }

    for component in question.expected_components:
        keywords = component_keywords.get(component, [])
        hits[component] = any(kw in context_lower for kw in keywords)

    return RetrievalScore(
        question_id=question.id,
        strategy=strategy,
        component_hits=hits,
    )


def print_comparison_table(scores: list[RetrievalScore]) -> None:
    """Print a formatted comparison of vector vs GraphRAG scores."""
    print("\n" + "=" * 70)
    print(f"{'Question':<12} {'Strategy':<12} {'Completeness':<15} {'Details'}")
    print("-" * 70)
    for s in sorted(scores, key=lambda x: (x.question_id, x.strategy)):
        details = ", ".join(
            f"{k}:{'Y' if v else 'N'}" for k, v in s.component_hits.items()
        )
        print(f"{s.question_id:<12} {s.strategy:<12} {s.completeness:<15.1%} {details}")
    print("=" * 70)


@pytest.mark.eval
class TestEvalQuestionDefinitions:
    """Validate the evaluation question set itself."""

    def test_all_questions_have_components(self):
        for q in EVAL_QUESTIONS:
            assert len(q.expected_components) > 0, f"{q.id} has no expected components"

    def test_question_ids_unique(self):
        ids = [q.id for q in EVAL_QUESTIONS]
        assert len(ids) == len(set(ids))

    def test_multi_hop_questions_exist(self):
        multi_hop = [q for q in EVAL_QUESTIONS if q.requires_multi_hop]
        assert len(multi_hop) >= 3

    def test_single_hop_baseline_exists(self):
        single_hop = [q for q in EVAL_QUESTIONS if not q.requires_multi_hop]
        assert len(single_hop) >= 1


@pytest.mark.eval
class TestScoringMechanism:
    def test_perfect_score(self):
        q = EvalQuestion(id="test", question="test?", expected_components=["regulation_title"])
        score = score_retrieval(q, "The GDPR regulation requires...", "vector")
        assert score.completeness == 1.0

    def test_zero_score(self):
        q = EvalQuestion(id="test", question="test?", expected_components=["system_name"])
        score = score_retrieval(q, "nothing relevant here", "vector")
        assert score.completeness == 0.0

    def test_partial_score(self):
        q = EvalQuestion(
            id="test",
            question="test?",
            expected_components=["system_name", "team_name"],
        )
        score = score_retrieval(q, "The CRM system is affected", "graphrag")
        assert 0.0 < score.completeness < 1.0
