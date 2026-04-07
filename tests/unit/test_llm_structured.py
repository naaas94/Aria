"""Structured LLM output parsing and repair retry."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from aria.llm.client import LLMClient


class _Tiny(BaseModel):
    value: int


@pytest.mark.asyncio
async def test_complete_structured_repair_succeeds_on_second_completion() -> None:
    client = LLMClient(max_retries=1)
    calls: list[int] = []

    async def fake_complete(_messages: list[dict[str, str]], **kwargs: object) -> str:
        calls.append(1)
        if len(calls) == 1:
            return "this is not valid json"
        return '{"value": 42}'

    with patch.object(client, "complete", side_effect=fake_complete):
        out = await client.complete_structured(
            [{"role": "user", "content": "emit json"}],
            _Tiny,
        )
    assert out.value == 42
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_complete_structured_no_repair_when_first_parse_ok() -> None:
    client = LLMClient(max_retries=1)

    async def fake_complete(_messages: list[dict[str, str]], **kwargs: object) -> str:
        return '{"value": 7}'

    with patch.object(client, "complete", side_effect=fake_complete) as p:
        out = await client.complete_structured(
            [{"role": "user", "content": "emit json"}],
            _Tiny,
        )
    assert out.value == 7
    assert p.await_count == 1
