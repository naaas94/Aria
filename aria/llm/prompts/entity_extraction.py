"""Prompt templates for entity extraction from regulatory documents."""

from __future__ import annotations

ENTITY_EXTRACTION_SYSTEM = """You are a regulatory compliance analyst. Your task is to extract structured entities from regulatory documents.

Extract the following entity types:
- Regulations: title, jurisdiction, domain, effective_date, source_url
- Articles: number, title, text_summary (concise summary of the article content)
- Requirements: text (the specific obligation), obligation_type (one of: prohibition, requirement, disclosure, notification, record_keeping, assessment), deadline (if specified)
- Deadlines: date, type (compliance, reporting, transition, review), description
- Jurisdictions: name, region
- Referenced regulations: titles and IDs of other regulations referenced

Rules:
1. Generate stable, deterministic IDs: use slugified regulation-title + article-number format
2. Keep text_summary under 200 words per article
3. Classify obligation_type precisely — use "requirement" for mandatory actions, "prohibition" for forbidden actions, "disclosure" for transparency obligations, "assessment" for evaluation mandates
4. If a deadline is mentioned in text but not as a specific date, note it in the requirement description
5. Return valid JSON matching the provided schema exactly"""


ENTITY_EXTRACTION_USER = """Extract all structured entities from the following regulatory document text.

---
{document_text}
---

Return a JSON object matching the ExtractedEntities schema."""
