"""ARIA_STRICT_SCHEMA_VERSION optional enforcement on contract models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aria.contracts.regulation import ExtractedEntities, SCHEMA_VERSION


def test_extracted_entities_accepts_any_schema_version_when_strict_unset() -> None:
    ExtractedEntities.model_validate(
        {"source_document_hash": "h", "schema_version": "9.9.9"},
    )


def test_extracted_entities_rejects_wrong_schema_version_when_strict_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARIA_STRICT_SCHEMA_VERSION", SCHEMA_VERSION)
    ExtractedEntities.model_validate(
        {"source_document_hash": "h", "schema_version": SCHEMA_VERSION},
    )
    with pytest.raises(ValidationError, match="schema_version"):
        ExtractedEntities.model_validate(
            {"source_document_hash": "h", "schema_version": "0.0.1"},
        )
