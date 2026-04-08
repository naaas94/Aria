"""Pydantic v2 schema for golden-set case definitions.

Each ``GoldenCase`` carries one or more *expectation lenses* (contract, trace,
retrieval, security) so a single scenario can be validated from multiple angles
without duplicating the input data.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Per-lens expectation models
# ---------------------------------------------------------------------------


class ExpectContract(BaseModel):
    """Structural / Pydantic-contract expectations."""

    model: str = Field(
        ...,
        description="Dotted import path to the Pydantic model, e.g. 'aria.contracts.impact.ImpactReport'",
    )
    required_fields: list[str] = Field(default_factory=list)
    schema_version: str | None = None
    fixture_data: dict[str, Any] | None = Field(
        default=None,
        description="Data dict to validate against the model (overrides input if set)",
    )


class ExpectTrace(BaseModel):
    """Orchestration trace / trajectory expectations."""

    expected_sequence: list[str] = Field(default_factory=list)
    forbidden_nodes: list[str] = Field(default_factory=list)
    max_steps: int | None = None
    required_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    must_have_error: bool = False
    must_not_have_error: bool = False


class ExpectRetrieval(BaseModel):
    """Retrieval quality expectations (component-keyword scoring)."""

    expected_components: list[str] = Field(default_factory=list)
    requires_multi_hop: bool = False
    component_keywords: dict[str, list[str]] = Field(default_factory=dict)


class ExpectSecurity(BaseModel):
    """Deterministic security-posture expectations."""

    expected_status: int | None = None
    must_not_contain: list[str] = Field(default_factory=list)
    must_contain: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    env_overrides: dict[str, str] = Field(default_factory=dict)
    method: str = "GET"
    path: str = ""
    json_body: dict[str, Any] | None = None
    check_type: str | None = Field(
        default=None,
        description="Named check function in runner, e.g. 'cypher_injection', 'error_disclosure'",
    )


class ExpectQuality(BaseModel):
    """Output quality expectations for LLM-generated answers."""

    must_mention: list[str] = Field(default_factory=list)
    must_not_mention: list[str] = Field(default_factory=list)
    min_source_count: int = 0
    max_answer_length: int | None = None
    answer_regex: str | None = Field(
        default=None,
        description="Regex pattern the answer text must match",
    )


class ExpectReplay(BaseModel):
    """Replay-based regression expectations against a recorded fixture."""

    fixture_file: str = Field(
        ...,
        description="Filename in replay/ directory, e.g. 'e2e-graphrag-gdpr-dpia.json'",
    )
    expected_strategy: str | None = None
    min_source_count: int = 0
    required_trace_keys: list[str] = Field(default_factory=list)
    quality: ExpectQuality | None = None


# ---------------------------------------------------------------------------
# Aggregate expectations
# ---------------------------------------------------------------------------


class Expectations(BaseModel):
    """Container for all lens-specific expectations on a single golden case."""

    contract: ExpectContract | None = None
    trace: ExpectTrace | None = None
    retrieval: ExpectRetrieval | None = None
    security: ExpectSecurity | None = None
    quality: ExpectQuality | None = None
    replay: ExpectReplay | None = None


# ---------------------------------------------------------------------------
# Top-level case model
# ---------------------------------------------------------------------------

Category = Literal["happy", "edge", "behavior_must", "behavior_must_not", "security"]
Tier = Literal["fast", "medium", "slow"]


class GoldenCase(BaseModel):
    """A single golden-set evaluation case."""

    id: str
    category: Category
    tier: Tier
    tags: list[str] = Field(default_factory=list)
    description: str = ""
    input: dict[str, Any] = Field(default_factory=dict)
    expect: Expectations
