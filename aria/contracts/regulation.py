"""Domain models for regulations, articles, requirements, and related entities.

These are the canonical schemas consumed by ingestion, graph builder, MCP tools,
and A2A envelopes. Any structural change here must be versioned.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from aria.contracts._strict import enforce_schema_version_if_configured

SCHEMA_VERSION = "0.1.0"


class ObligationType(StrEnum):
    PROHIBITION = "prohibition"
    REQUIREMENT = "requirement"
    DISCLOSURE = "disclosure"
    NOTIFICATION = "notification"
    RECORD_KEEPING = "record_keeping"
    ASSESSMENT = "assessment"


class DeadlineType(StrEnum):
    COMPLIANCE = "compliance"
    REPORTING = "reporting"
    TRANSITION = "transition"
    REVIEW = "review"


class Jurisdiction(BaseModel):
    id: str = Field(..., description="Unique jurisdiction identifier")
    name: str
    region: str = Field(..., description="Geographic region (EU, US, APAC, etc.)")


class Deadline(BaseModel):
    id: str
    date: date
    type: DeadlineType
    article_id: str
    description: str = ""


class Requirement(BaseModel):
    id: str
    text: str
    obligation_type: ObligationType
    deadline: date | None = None
    description: str = ""


class Article(BaseModel):
    id: str
    number: str = Field(..., description="Article number within the regulation")
    title: str
    text_summary: str
    regulation_id: str
    requirements: list[Requirement] = Field(default_factory=list)
    deadlines: list[Deadline] = Field(default_factory=list)


class Regulation(BaseModel):
    id: str
    title: str
    jurisdiction: str
    domain: str = Field(..., description="Regulatory domain (privacy, AI, finance, etc.)")
    effective_date: date | None = None
    source_url: str = ""
    articles: list[Article] = Field(default_factory=list)
    amends: list[str] = Field(default_factory=list, description="IDs of amended regulations")
    references: list[str] = Field(
        default_factory=list, description="IDs of referenced regulations"
    )


class PolicyDocument(BaseModel):
    id: str
    title: str
    owner_team: str
    version: str = "1.0"
    last_reviewed: date | None = None


class InternalSystem(BaseModel):
    id: str
    name: str
    description: str = ""
    category: str = Field(..., description="System category (HR, ML, CRM, etc.)")
    owner_team: str
    data_types: list[str] = Field(default_factory=list)


class Team(BaseModel):
    id: str
    name: str
    function: str = ""
    contact: str = ""


class ExtractedEntities(BaseModel):
    """Output of the entity extraction agent — all entities found in a single document."""

    schema_version: str = SCHEMA_VERSION
    source_document_hash: str = Field(
        ..., description="Content hash for idempotency tracking"
    )
    regulations: list[Regulation] = Field(default_factory=list)
    jurisdictions: list[Jurisdiction] = Field(default_factory=list)
    teams: list[Team] = Field(default_factory=list)
    policy_documents: list[PolicyDocument] = Field(default_factory=list)
    internal_systems: list[InternalSystem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _strict_schema_version(self) -> ExtractedEntities:
        enforce_schema_version_if_configured(self)
        return self
