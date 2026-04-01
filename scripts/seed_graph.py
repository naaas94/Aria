"""Populate Neo4j with sample regulatory data (GDPR, EU AI Act subset).

Run: python scripts/seed_graph.py
Requires: Neo4j running (docker compose up neo4j)
"""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

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
from aria.graph.builder import entities_to_write_payload, write_payload
from aria.graph.client import Neo4jClient


def build_seed_entities() -> ExtractedEntities:
    """Build a representative sample dataset for development and testing."""

    jurisdictions = [
        Jurisdiction(id="eu", name="European Union", region="EU"),
        Jurisdiction(id="us-ca", name="California", region="US"),
    ]

    teams = [
        Team(id="team-eng", name="Engineering", function="Software Development", contact="eng@example.com"),
        Team(id="team-legal", name="Legal & Compliance", function="Legal Affairs", contact="legal@example.com"),
        Team(id="team-data", name="Data Science", function="ML & Analytics", contact="data@example.com"),
        Team(id="team-hr", name="Human Resources", function="People Operations", contact="hr@example.com"),
    ]

    systems = [
        InternalSystem(id="sys-crm", name="Customer CRM", category="CRM", owner_team="team-eng", data_types=["personal_data", "contact_info"]),
        InternalSystem(id="sys-ml-risk", name="ML Risk Scoring", category="ML", owner_team="team-data", data_types=["personal_data", "financial_data"]),
        InternalSystem(id="sys-hr-platform", name="HR Platform", category="HR", owner_team="team-hr", data_types=["employee_data", "biometric_data"]),
        InternalSystem(id="sys-chatbot", name="Customer Chatbot", category="AI", owner_team="team-eng", data_types=["personal_data", "interaction_logs"]),
    ]

    policies = [
        PolicyDocument(id="pol-privacy", title="Data Privacy Policy", owner_team="team-legal", version="3.1"),
        PolicyDocument(id="pol-ai-ethics", title="AI Ethics Guidelines", owner_team="team-data", version="1.0"),
    ]

    gdpr = Regulation(
        id="reg-gdpr",
        title="General Data Protection Regulation",
        jurisdiction="eu",
        domain="privacy",
        effective_date="2018-05-25",
        source_url="https://eur-lex.europa.eu/eli/reg/2016/679/oj",
        articles=[
            Article(
                id="art-gdpr-5",
                number="5",
                title="Principles relating to processing of personal data",
                text_summary="Personal data must be processed lawfully, fairly, and transparently.",
                regulation_id="reg-gdpr",
                requirements=[
                    Requirement(id="req-gdpr-5-1", text="Process personal data lawfully, fairly and in a transparent manner", obligation_type=ObligationType.REQUIREMENT),
                    Requirement(id="req-gdpr-5-2", text="Collect data for specified, explicit and legitimate purposes", obligation_type=ObligationType.REQUIREMENT),
                ],
            ),
            Article(
                id="art-gdpr-17",
                number="17",
                title="Right to erasure (right to be forgotten)",
                text_summary="Data subjects have the right to obtain erasure of personal data.",
                regulation_id="reg-gdpr",
                requirements=[
                    Requirement(id="req-gdpr-17-1", text="Erase personal data without undue delay when requested by data subject", obligation_type=ObligationType.REQUIREMENT),
                ],
            ),
            Article(
                id="art-gdpr-35",
                number="35",
                title="Data protection impact assessment",
                text_summary="DPIA required for processing likely to result in high risk.",
                regulation_id="reg-gdpr",
                requirements=[
                    Requirement(id="req-gdpr-35-1", text="Carry out data protection impact assessment before high-risk processing", obligation_type=ObligationType.ASSESSMENT),
                ],
            ),
        ],
    )

    eu_ai_act = Regulation(
        id="reg-eu-ai-act",
        title="EU AI Act",
        jurisdiction="eu",
        domain="AI",
        effective_date="2025-08-01",
        source_url="https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
        references=["reg-gdpr"],
        articles=[
            Article(
                id="art-ai-6",
                number="6",
                title="Classification rules for high-risk AI systems",
                text_summary="AI systems in Annex III areas are classified as high-risk.",
                regulation_id="reg-eu-ai-act",
                requirements=[
                    Requirement(id="req-ai-6-1", text="Classify AI systems according to risk categories before deployment", obligation_type=ObligationType.ASSESSMENT),
                ],
                deadlines=[
                    Deadline(id="dl-ai-6", date="2025-08-01", type=DeadlineType.COMPLIANCE, article_id="art-ai-6", description="High-risk AI classification deadline"),
                ],
            ),
            Article(
                id="art-ai-9",
                number="9",
                title="Risk management system",
                text_summary="Providers of high-risk AI systems shall establish a risk management system.",
                regulation_id="reg-eu-ai-act",
                requirements=[
                    Requirement(id="req-ai-9-1", text="Establish and maintain a risk management system for high-risk AI", obligation_type=ObligationType.REQUIREMENT),
                    Requirement(id="req-ai-9-2", text="Risk management must include identification and analysis of known risks", obligation_type=ObligationType.ASSESSMENT),
                ],
            ),
            Article(
                id="art-ai-52",
                number="52",
                title="Transparency obligations for certain AI systems",
                text_summary="Providers must ensure AI systems interacting with humans disclose they are AI.",
                regulation_id="reg-eu-ai-act",
                requirements=[
                    Requirement(id="req-ai-52-1", text="Disclose to users that they are interacting with an AI system", obligation_type=ObligationType.DISCLOSURE),
                ],
                deadlines=[
                    Deadline(id="dl-ai-52", date="2025-08-01", type=DeadlineType.COMPLIANCE, article_id="art-ai-52", description="Transparency obligation deadline"),
                ],
            ),
        ],
    )

    return ExtractedEntities(
        source_document_hash="seed-data-v1",
        regulations=[gdpr, eu_ai_act],
        jurisdictions=jurisdictions,
        teams=teams,
        internal_systems=systems,
        policy_documents=policies,
    )


async def main() -> None:
    load_dotenv()
    client = Neo4jClient(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "aria_dev_password"),
    )
    await client.connect()

    try:
        await client.initialize_schema()
        entities = build_seed_entities()
        payload = entities_to_write_payload(entities)
        status = await write_payload(client, payload)
        print(f"Nodes created: {status.nodes_created}, merged: {status.nodes_merged}")
        print(f"Edges created: {status.edges_created}, merged: {status.edges_merged}")
        if status.errors:
            print(f"Errors: {status.errors}")
        else:
            print("Seed complete — no errors.")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
