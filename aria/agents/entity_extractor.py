"""Entity extractor agent — LLM-powered entity and relationship extraction.

Receives structured document chunks and extracts regulatory entities
(regulations, articles, requirements, etc.) using the LLM client.
All output is validated against Pydantic contracts.
"""

from __future__ import annotations

from typing import Any

from aria.agents.base import BaseAgent
from aria.contracts.regulation import ExtractedEntities
from aria.llm.client import LLMClient
from aria.llm.prompts.entity_extraction import (
    ENTITY_EXTRACTION_SYSTEM,
    ENTITY_EXTRACTION_USER,
)


class EntityExtractorAgent(BaseAgent):
    name = "entity_extractor"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        super().__init__()
        self._llm = llm_client or LLMClient()

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        document_text = input_data.get("document_text", "")
        document_hash = input_data.get("document_hash", "unknown")

        if not document_text:
            raise ValueError("No document_text provided to entity extractor")

        messages = [
            {"role": "system", "content": ENTITY_EXTRACTION_SYSTEM},
            {
                "role": "user",
                "content": ENTITY_EXTRACTION_USER.format(document_text=document_text),
            },
        ]

        entities = await self._llm.complete_structured(
            messages, ExtractedEntities
        )
        entities.source_document_hash = document_hash

        self.logger.info(
            "Extracted %d regulations, %d jurisdictions from document",
            len(entities.regulations), len(entities.jurisdictions),
        )

        return entities.model_dump()
