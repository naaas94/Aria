"""Unit tests for entity extraction contracts and agent logic."""

from __future__ import annotations

import pytest

from aria.contracts.regulation import (
    Article,
    ExtractedEntities,
    ObligationType,
    Regulation,
    Requirement,
)
from aria.agents.supervisor import SupervisorAgent


class TestExtractedEntitiesContract:
    def test_empty_entities_valid(self):
        entities = ExtractedEntities(
            source_document_hash="abc123",
        )
        assert entities.schema_version == "0.1.0"
        assert len(entities.regulations) == 0

    def test_full_entities_serialization(self):
        entities = ExtractedEntities(
            source_document_hash="hash123",
            regulations=[
                Regulation(
                    id="reg-1",
                    title="Test Regulation",
                    jurisdiction="eu",
                    domain="privacy",
                    articles=[
                        Article(
                            id="art-1",
                            number="1",
                            title="Scope",
                            text_summary="Defines scope",
                            regulation_id="reg-1",
                            requirements=[
                                Requirement(
                                    id="req-1",
                                    text="Must comply",
                                    obligation_type=ObligationType.REQUIREMENT,
                                )
                            ],
                        )
                    ],
                )
            ],
        )
        data = entities.model_dump()
        assert data["regulations"][0]["articles"][0]["requirements"][0]["obligation_type"] == "requirement"

        roundtrip = ExtractedEntities.model_validate(data)
        assert roundtrip.regulations[0].id == "reg-1"

    def test_obligation_types(self):
        for ot in ObligationType:
            req = Requirement(id="r", text="t", obligation_type=ot)
            assert req.obligation_type == ot


class TestSupervisorAgent:
    @pytest.mark.asyncio
    async def test_classify_ingestion(self):
        agent = SupervisorAgent()
        result = await agent.process({"raw_document": "some content"})
        assert result["intent"] == "ingestion"

    @pytest.mark.asyncio
    async def test_classify_impact_query(self):
        agent = SupervisorAgent()
        result = await agent.process({"regulation_id": "reg-gdpr"})
        assert result["intent"] == "impact_query"

    @pytest.mark.asyncio
    async def test_classify_free_query(self):
        agent = SupervisorAgent()
        result = await agent.process({"query": "What regulations affect us?"})
        assert result["intent"] == "free_query"

    @pytest.mark.asyncio
    async def test_classify_unknown(self):
        agent = SupervisorAgent()
        result = await agent.process({})
        assert result["intent"] == "unknown"

    @pytest.mark.asyncio
    async def test_agent_lifecycle(self):
        agent = SupervisorAgent()
        result = await agent.run({"regulation_id": "reg-1"})
        assert result.success
        assert result.agent_name == "supervisor"
        assert result.duration_ms >= 0
