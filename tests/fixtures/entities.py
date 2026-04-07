"""Pre-built ExtractedEntities for tests — uses aria.contracts.regulation only."""

from __future__ import annotations

from datetime import date

from aria.contracts.regulation import (
    Article,
    Deadline,
    DeadlineType,
    ExtractedEntities,
    InternalSystem,
    Jurisdiction,
    ObligationType,
    PolicyDocument,
    Regulation,
    Requirement,
    Team,
)

from scripts.seed_graph import build_seed_entities

# ---------------------------------------------------------------------------
# Happy path (≥3)
# ---------------------------------------------------------------------------

HAPPY_FULL_GDPR_AND_AI_ACT: ExtractedEntities = build_seed_entities()

HAPPY_MINIMAL_SINGLE_CHAIN = ExtractedEntities(
    source_document_hash="fixture-minimal-v1",
    jurisdictions=[
        Jurisdiction(id="eu", name="European Union", region="EU"),
    ],
    teams=[
        Team(id="team-solo", name="Solo Team", function="Compliance", contact="solo@example.com"),
    ],
    internal_systems=[],
    policy_documents=[],
    regulations=[
        Regulation(
            id="reg-minimal",
            title="Minimal Test Regulation",
            jurisdiction="eu",
            domain="test",
            effective_date=date(2026, 1, 1),
            source_url="https://example.invalid/reg/minimal",
            articles=[
                Article(
                    id="art-minimal-1",
                    number="1",
                    title="Single article",
                    text_summary="One article, one requirement.",
                    regulation_id="reg-minimal",
                    requirements=[
                        Requirement(
                            id="req-minimal-1",
                            text="Do the one thing that is required.",
                            obligation_type=ObligationType.REQUIREMENT,
                        ),
                    ],
                ),
            ],
        ),
    ],
)

HAPPY_FICTIONAL_DSA_WITH_CROSS_REF = ExtractedEntities(
    source_document_hash="fixture-fic-dsa-v1",
    jurisdictions=[
        Jurisdiction(id="eu", name="European Union", region="EU"),
    ],
    teams=[
        Team(id="team-trust", name="Trust & Safety", function="Moderation", contact="trust@example.com"),
    ],
    internal_systems=[
        InternalSystem(
            id="sys-feed",
            name="Content Feed Service",
            category="Platform",
            owner_team="team-trust",
            data_types=["user_generated_content"],
        ),
    ],
    policy_documents=[
        PolicyDocument(
            id="pol-moderation",
            title="Content Moderation Playbook",
            owner_team="team-trust",
            version="2.0",
            last_reviewed=date(2026, 3, 1),
        ),
    ],
    regulations=[
        Regulation(
            id="reg-fic-dsa",
            title="Fictional Digital Services Act 2026",
            jurisdiction="eu",
            domain="platform_governance",
            effective_date=date(2026, 6, 1),
            source_url="https://example.invalid/fic-dsa",
            references=["reg-gdpr"],
            articles=[
                Article(
                    id="art-fic-14",
                    number="14",
                    title="Illegal content moderation",
                    text_summary="Expeditious takedown and transparency reporting.",
                    regulation_id="reg-fic-dsa",
                    requirements=[
                        Requirement(
                            id="req-fic-14-1",
                            text="Act expeditiously on manifestly illegal content orders.",
                            obligation_type=ObligationType.REQUIREMENT,
                        ),
                        Requirement(
                            id="req-fic-14-2",
                            text="Publish annual transparency reports on orders received.",
                            obligation_type=ObligationType.DISCLOSURE,
                        ),
                    ],
                    deadlines=[
                        Deadline(
                            id="dl-fic-14",
                            date=date(2026, 6, 1),
                            type=DeadlineType.COMPLIANCE,
                            article_id="art-fic-14",
                            description="Moderation process compliance date",
                        ),
                    ],
                ),
            ],
        ),
        Regulation(
            id="reg-gdpr",
            title="GDPR (stub for cross-reference testing)",
            jurisdiction="eu",
            domain="privacy",
            effective_date=date(2018, 5, 25),
            source_url="https://eur-lex.europa.eu/eli/reg/2016/679/oj",
            articles=[],
        ),
    ],
)

# ---------------------------------------------------------------------------
# Adversarial / edge (≥5)
# ---------------------------------------------------------------------------

ADV_EMPTY_ENTITY_COLLECTIONS = ExtractedEntities(
    source_document_hash="fixture-empty-collections",
    regulations=[],
    jurisdictions=[],
    teams=[],
    policy_documents=[],
    internal_systems=[],
)

ADV_DUPLICATE_REQUIREMENT_IDS = ExtractedEntities(
    source_document_hash="fixture-dup-req-ids",
    jurisdictions=[Jurisdiction(id="eu", name="EU", region="EU")],
    teams=[],
    policy_documents=[],
    internal_systems=[],
    regulations=[
        Regulation(
            id="reg-dup",
            title="Duplicate requirement IDs",
            jurisdiction="eu",
            domain="test",
            articles=[
                Article(
                    id="art-a",
                    number="1",
                    title="Article A",
                    text_summary="",
                    regulation_id="reg-dup",
                    requirements=[
                        Requirement(
                            id="req-SAME-ID",
                            text="First occurrence",
                            obligation_type=ObligationType.REQUIREMENT,
                        ),
                    ],
                ),
                Article(
                    id="art-b",
                    number="2",
                    title="Article B",
                    text_summary="",
                    regulation_id="reg-dup",
                    requirements=[
                        Requirement(
                            id="req-SAME-ID",
                            text="Second occurrence — same id",
                            obligation_type=ObligationType.NOTIFICATION,
                        ),
                    ],
                ),
            ],
        ),
    ],
)

ADV_CIRCULAR_AMENDS = ExtractedEntities(
    source_document_hash="fixture-circular-amends",
    jurisdictions=[Jurisdiction(id="eu", name="EU", region="EU")],
    teams=[],
    policy_documents=[],
    internal_systems=[],
    regulations=[
        Regulation(
            id="reg-alpha",
            title="Regulation Alpha",
            jurisdiction="eu",
            domain="test",
            amends=["reg-beta"],
            articles=[],
        ),
        Regulation(
            id="reg-beta",
            title="Regulation Beta",
            jurisdiction="eu",
            domain="test",
            amends=["reg-alpha"],
            articles=[],
        ),
    ],
)

ADV_CIRCULAR_REFERENCES = ExtractedEntities(
    source_document_hash="fixture-circular-refs",
    jurisdictions=[Jurisdiction(id="eu", name="EU", region="EU")],
    teams=[],
    policy_documents=[],
    internal_systems=[],
    regulations=[
        Regulation(
            id="reg-refs-a",
            title="Refs A",
            jurisdiction="eu",
            domain="test",
            references=["reg-refs-b"],
            articles=[],
        ),
        Regulation(
            id="reg-refs-b",
            title="Refs B",
            jurisdiction="eu",
            domain="test",
            references=["reg-refs-a"],
            articles=[],
        ),
    ],
)

ADV_JURISDICTION_KEY_ORPHAN = ExtractedEntities(
    source_document_hash="fixture-orphan-jurisdiction-key",
    jurisdictions=[
        Jurisdiction(id="eu", name="European Union", region="EU"),
    ],
    teams=[],
    policy_documents=[],
    internal_systems=[],
    regulations=[
        Regulation(
            id="reg-orphan-jur",
            title="Regulation pointing at missing jurisdiction node",
            jurisdiction="missing-jur-id",
            domain="test",
            articles=[
                Article(
                    id="art-orphan",
                    number="1",
                    title="Orphan jurisdiction link",
                    text_summary="jurisdiction id not in jurisdictions list",
                    regulation_id="reg-orphan-jur",
                    requirements=[],
                ),
            ],
        ),
    ],
)

ADV_UNICODE_AND_EMPTY_STRING_FIELDS = ExtractedEntities(
    source_document_hash="fixture-unicode-empty-fields",
    jurisdictions=[
        Jurisdiction(id="jp", name="日本", region="APAC"),
    ],
    teams=[
        Team(id="team-unicode", name="", function="", contact=""),
    ],
    policy_documents=[],
    internal_systems=[],
    regulations=[
        Regulation(
            id="reg-unicode",
            title="",
            jurisdiction="jp",
            domain="privacy",
            source_url="",
            articles=[
                Article(
                    id="art-unicode-1",
                    number="Ω-1",
                    title="記録義務 — Record keeping",
                    text_summary="Emoji test 📋 — empty title on regulation level only",
                    regulation_id="reg-unicode",
                    requirements=[
                        Requirement(
                            id="req-unicode-1",
                            text="Keep records of processing activities — 処理記録",
                            obligation_type=ObligationType.RECORD_KEEPING,
                            description="",
                        ),
                    ],
                ),
            ],
        ),
    ],
)
