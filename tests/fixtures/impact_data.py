"""Sample graph query row dicts matching aria.graph.queries Cypher RETURN shapes.

Columns align with ``impact_by_regulation`` and ``uncovered_requirements``.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# impact_by_regulation — happy path (≥3)
# ---------------------------------------------------------------------------

IMPACT_BY_REGULATION_HAPPY_FULL_COVERAGE: list[dict[str, Any]] = [
    {
        "regulation": "General Data Protection Regulation",
        "article": "5",
        "article_id": "art-gdpr-5",
        "requirement_id": "req-gdpr-5-1",
        "requirement": "Process personal data lawfully, fairly and in a transparent manner",
        "obligation_type": "requirement",
        "system_id": "sys-crm",
        "system_name": "Customer CRM",
        "team": "Engineering",
        "team_id": "team-eng",
        "policy_id": "pol-privacy",
        "policy_title": "Data Privacy Policy",
    },
    {
        "regulation": "General Data Protection Regulation",
        "article": "17",
        "article_id": "art-gdpr-17",
        "requirement_id": "req-gdpr-17-1",
        "requirement": "Erase personal data without undue delay when requested by data subject",
        "obligation_type": "requirement",
        "system_id": "sys-crm",
        "system_name": "Customer CRM",
        "team": "Engineering",
        "team_id": "team-eng",
        "policy_id": "pol-privacy",
        "policy_title": "Data Privacy Policy",
    },
]

IMPACT_BY_REGULATION_HAPPY_MIXED_COVERAGE: list[dict[str, Any]] = [
    {
        "regulation": "EU AI Act",
        "article": "9",
        "article_id": "art-ai-9",
        "requirement_id": "req-ai-9-1",
        "requirement": "Establish and maintain a risk management system for high-risk AI",
        "obligation_type": "requirement",
        "system_id": "sys-ml-risk",
        "system_name": "ML Risk Scoring",
        "team": "Data Science",
        "team_id": "team-data",
        "policy_id": "pol-ai-ethics",
        "policy_title": "AI Ethics Guidelines",
    },
    {
        "regulation": "EU AI Act",
        "article": "52",
        "article_id": "art-ai-52",
        "requirement_id": "req-ai-52-1",
        "requirement": "Disclose to users that they are interacting with an AI system",
        "obligation_type": "disclosure",
        "system_id": "sys-chatbot",
        "system_name": "Customer Chatbot",
        "team": "Engineering",
        "team_id": "team-eng",
        "policy_id": None,
        "policy_title": None,
    },
]

IMPACT_BY_REGULATION_HAPPY_SINGLE_ROW: list[dict[str, Any]] = [
    {
        "regulation": "Fictional Digital Services Act 2026",
        "article": "14",
        "article_id": "art-fic-14",
        "requirement_id": "req-fic-14-1",
        "requirement": "Act expeditiously on manifestly illegal content orders.",
        "obligation_type": "requirement",
        "system_id": "sys-feed",
        "system_name": "Content Feed Service",
        "team": "Trust & Safety",
        "team_id": "team-trust",
        "policy_id": "pol-moderation",
        "policy_title": "Content Moderation Playbook",
    },
]

# ---------------------------------------------------------------------------
# impact_by_regulation — adversarial / edge (≥5)
# ---------------------------------------------------------------------------

IMPACT_BY_REG_ADV_EMPTY_RESULT: list[dict[str, Any]] = []

IMPACT_BY_REG_ADV_SPARSE_KEYS: list[dict[str, Any]] = [
    {
        "regulation": "Unknown Regulation",
        "article": None,
        "article_id": None,
        "requirement_id": None,
        "requirement": "",
        "obligation_type": "requirement",
        "system_id": None,
        "system_name": None,
        "team": None,
        "team_id": None,
        "policy_id": None,
        "policy_title": None,
    },
]

IMPACT_BY_REG_ADV_DUPLICATE_ROWS_SAME_REQ: list[dict[str, Any]] = [
    {
        "regulation": "GDPR",
        "article": "5",
        "article_id": "art-gdpr-5",
        "requirement_id": "req-dup",
        "requirement": "Duplicate row same requirement",
        "obligation_type": "requirement",
        "system_id": "sys-1",
        "system_name": "System One",
        "team": "Team A",
        "team_id": "team-a",
        "policy_id": None,
        "policy_title": None,
    },
    {
        "regulation": "GDPR",
        "article": "5",
        "article_id": "art-gdpr-5",
        "requirement_id": "req-dup",
        "requirement": "Duplicate row same requirement",
        "obligation_type": "requirement",
        "system_id": "sys-2",
        "system_name": "System Two",
        "team": "Team B",
        "team_id": "team-b",
        "policy_id": None,
        "policy_title": None,
    },
]

IMPACT_BY_REG_ADV_UNICODE_VALUES: list[dict[str, Any]] = [
    {
        "regulation": "規制サンプル — Règlement",
        "article": "Ω-9",
        "article_id": "art-uni-9",
        "requirement_id": "req-uni-1",
        "requirement": "処理の透明性 — transparence 📋",
        "obligation_type": "disclosure",
        "system_id": "sys-unicode",
        "system_name": "システム名",
        "team": "チーム",
        "team_id": "team-jp",
        "policy_id": None,
        "policy_title": None,
    },
]

IMPACT_BY_REG_ADV_SUSPICIOUS_STRINGS: list[dict[str, Any]] = [
    {
        "regulation": "'; DROP CONSTRAINT neo4j; --",
        "article": "<script>",
        "article_id": "art-xss",
        "requirement_id": "req-xss",
        "requirement": "{{constructor.constructor('return this')()}}",
        "obligation_type": "requirement",
        "system_id": "sys-ok",
        "system_name": "Normal System",
        "team": "Team",
        "team_id": "team-ok",
        "policy_id": "pol-ok",
        "policy_title": "Policy",
    },
]

IMPACT_BY_REG_ADV_HUGE_TEXT: list[dict[str, Any]] = [
    {
        "regulation": "Stress Test Regulation",
        "article": "1",
        "article_id": "art-huge",
        "requirement_id": "req-huge",
        "requirement": "Preamble " + ("word " * 5000),
        "obligation_type": "requirement",
        "system_id": "sys-huge",
        "system_name": "Huge",
        "team": "Team",
        "team_id": "team-huge",
        "policy_id": None,
        "policy_title": None,
    },
]

# ---------------------------------------------------------------------------
# uncovered_requirements — happy path (≥3)
# ---------------------------------------------------------------------------

UNCOVERED_REQUIREMENTS_HAPPY_SINGLE_GAP: list[dict[str, Any]] = [
    {
        "regulation": "EU AI Act",
        "article": "52",
        "requirement": "Disclose to users that they are interacting with an AI system",
        "obligation_type": "disclosure",
        "system": "Customer Chatbot",
        "team": "Engineering",
    },
]

UNCOVERED_REQUIREMENTS_HAPPY_MULTIPLE: list[dict[str, Any]] = [
    {
        "regulation": "General Data Protection Regulation",
        "article": "35",
        "requirement": "Carry out data protection impact assessment before high-risk processing",
        "obligation_type": "assessment",
        "system": "ML Risk Scoring",
        "team": "Data Science",
    },
    {
        "regulation": "General Data Protection Regulation",
        "article": "17",
        "requirement": "Erase personal data without undue delay when requested by data subject",
        "obligation_type": "requirement",
        "system": "HR Platform",
        "team": "Human Resources",
    },
]

UNCOVERED_REQUIREMENTS_HAPPY_NONE_ELSEWHERE_COVERED: list[dict[str, Any]] = [
    {
        "regulation": "Fictional Digital Services Act 2026",
        "article": "14",
        "requirement": "Publish annual transparency reports on orders received.",
        "obligation_type": "disclosure",
        "system": "Content Feed Service",
        "team": "Trust & Safety",
    },
]

# ---------------------------------------------------------------------------
# uncovered_requirements — adversarial / edge (≥5)
# ---------------------------------------------------------------------------

UNCOVERED_REQUIREMENTS_ADV_EMPTY: list[dict[str, Any]] = []

UNCOVERED_REQUIREMENTS_ADV_NULL_LIKE_STRINGS: list[dict[str, Any]] = [
    {
        "regulation": "null",
        "article": "None",
        "requirement": "",
        "obligation_type": "requirement",
        "system": "undefined",
        "team": "false",
    },
]

UNCOVERED_REQUIREMENTS_ADV_DUPLICATE_LINES: list[dict[str, Any]] = [
    {
        "regulation": "Reg X",
        "article": "1",
        "requirement": "Same text",
        "obligation_type": "requirement",
        "system": "Sys",
        "team": "T",
    },
    {
        "regulation": "Reg X",
        "article": "1",
        "requirement": "Same text",
        "obligation_type": "requirement",
        "system": "Sys",
        "team": "T",
    },
]

UNCOVERED_REQUIREMENTS_ADV_SPECIAL_OBLIGATION: list[dict[str, Any]] = [
    {
        "regulation": "Custom Act",
        "article": "99",
        "requirement": "Notify supervisory authority within 72 hours",
        "obligation_type": "notification",
        "system": "Incident Bot",
        "team": "Security",
    },
]

UNCOVERED_REQUIREMENTS_ADV_MIXED_UNICODE: list[dict[str, Any]] = [
    {
        "regulation": "Verordnung 例",
        "article": "½",
        "requirement": "Straße größer als ß",
        "obligation_type": "prohibition",
        "system": "Système",
        "team": "Équipe",
    },
]

UNCOVERED_REQUIREMENTS_ADV_LONG_TEAM_NAME: list[dict[str, Any]] = [
    {
        "regulation": "Reg",
        "article": "1",
        "requirement": "Do something",
        "obligation_type": "requirement",
        "system": "S",
        "team": "Team " + ("A" * 400),
    },
]
