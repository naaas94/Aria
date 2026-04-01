"""Supervisor agent — routes and delegates to sub-agents.

Receives user queries or system triggers, classifies intent, and
routes to the appropriate sub-agent pipeline via the orchestration graph.
"""

from __future__ import annotations

from typing import Any

from aria.agents.base import BaseAgent


class SupervisorAgent(BaseAgent):
    name = "supervisor"

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Classify intent and determine routing.

        Returns a routing decision dict consumed by the orchestration engine.
        """
        intent = self._classify_intent(input_data)
        self.logger.info("Classified intent: %s", intent)

        return {
            "intent": intent,
            "regulation_id": input_data.get("regulation_id"),
            "raw_document": input_data.get("raw_document"),
            "query": input_data.get("query"),
        }

    def _classify_intent(self, input_data: dict[str, Any]) -> str:
        if input_data.get("raw_document"):
            return "ingestion"
        if input_data.get("regulation_id"):
            if input_data.get("query"):
                return "gap_analysis"
            return "impact_query"
        if input_data.get("query"):
            return "free_query"
        return "unknown"
