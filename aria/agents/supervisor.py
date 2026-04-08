"""Supervisor agent — routes and delegates to sub-agents.

Receives user queries or system triggers, classifies intent, and
routes to the appropriate sub-agent pipeline via the orchestration graph.

Intent labels vs scratch graph (``aria.orchestration.scratch.edges``)
--------------------------------------------------------------------
The graph keys off ``ARIAState`` fields, not the string ``intent`` returned
here. Mapping for the default scratch graph:

- **ingestion** — ``raw_document`` set → ``supervisor`` → ``ingestion`` →
  ``entity_extractor`` → ``graph_builder`` (→ impact chain if
  ``regulation_id`` present on state).
- **impact_query** / **gap_analysis** — ``regulation_id`` set and no
  ``raw_document`` → ``impact_analyzer`` (same path; ``query`` does not
  change the edge today).
- **free_query** — only ``query`` (no regulation id, no document) →
  ``free_query`` (vector search).
- **unknown** — no actionable fields → ``supervisor`` → ``end``.
"""

from __future__ import annotations

from typing import Any

from aria.agents.base import BaseAgent


class SupervisorAgent(BaseAgent):
    name = "supervisor"

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Classify intent and determine routing.

        Returns a routing decision dict consumed by the orchestration engine.
        Callers must populate ``ARIAState`` from this dict (or equivalent)
        so ``route_after_supervisor`` can branch.
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
