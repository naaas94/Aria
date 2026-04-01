"""Agent Card — structured capability descriptor following the A2A spec.

Each ARIA agent publishes a card describing its capabilities, expected
input/output schemas, and endpoint. Cards are the discovery primitive
that enables delegation without coupling to internal implementations.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

PROTOCOL_VERSION = "0.1"


class AgentCard(BaseModel):
    """A2A Agent Card — the public contract of an agent's capabilities."""

    agent_id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Human-readable agent name")
    version: str = Field(default="0.1.0")
    description: str = Field(default="")
    capabilities: list[str] = Field(
        default_factory=list,
        description="List of capability tags this agent supports",
    )
    input_schema: str = Field(
        default="",
        description="Name of the Pydantic model for input validation",
    )
    output_schema: str = Field(
        default="",
        description="Name of the Pydantic model for output validation",
    )
    endpoint: str = Field(
        default="",
        description="HTTP endpoint for A2A task delegation",
    )
    protocol_version: str = Field(default=PROTOCOL_VERSION)

    def supports_capability(self, capability: str) -> bool:
        return capability in self.capabilities


AGENT_CARDS: dict[str, AgentCard] = {
    "supervisor": AgentCard(
        agent_id="supervisor-01",
        name="Supervisor",
        description="Orchestrator agent — classifies intent and routes to sub-agents",
        capabilities=["intent_classification", "orchestration"],
        input_schema="dict",
        output_schema="dict",
    ),
    "ingestion_agent": AgentCard(
        agent_id="ingestion-01",
        name="Ingestion Agent",
        description="Triggers and monitors document ingestion pipeline",
        capabilities=["document_ingestion", "parsing"],
        input_schema="dict",
        output_schema="dict",
    ),
    "entity_extractor": AgentCard(
        agent_id="entity-extractor-01",
        name="Entity Extractor",
        description="LLM-powered entity and relationship extraction from regulatory documents",
        capabilities=["entity_extraction", "llm_processing"],
        input_schema="ExtractedEntities",
        output_schema="ExtractedEntities",
    ),
    "graph_builder": AgentCard(
        agent_id="graph-builder-01",
        name="Graph Builder",
        description="Translates extracted entities into idempotent Neo4j MERGE operations",
        capabilities=["graph_writing", "entity_mapping"],
        input_schema="ExtractedEntities",
        output_schema="GraphWriteStatus",
    ),
    "impact_analyzer": AgentCard(
        agent_id="impact-analyzer-01",
        name="Impact Analyzer",
        description="Multi-hop graph traversal for regulatory impact assessment",
        capabilities=["regulatory_impact_analysis", "multi_hop_graph_traversal"],
        input_schema="ImpactAnalysisRequest",
        output_schema="ImpactReport",
        endpoint="http://localhost:8001/a2a",
    ),
    "report_generator": AgentCard(
        agent_id="report-generator-01",
        name="Report Generator",
        description="Generates human-readable compliance reports from impact analysis",
        capabilities=["report_generation", "llm_processing"],
        input_schema="ImpactReport",
        output_schema="dict",
        endpoint="http://localhost:8002/a2a",
    ),
}
