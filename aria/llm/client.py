"""LiteLLM wrapper with retry, timeout, and structured output support.

Provides a unified interface to local (Ollama) and remote LLM providers.
All agent LLM calls go through this client.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, TypeVar

import litellm
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

litellm.drop_params = True


class LLMClient:
    """Thin wrapper around LiteLLM for consistent agent LLM access."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        max_retries: int = 3,
        timeout: float = 120.0,
    ) -> None:
        self.model = model or os.getenv("LLM_MODEL", "ollama/llama3.2")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "http://localhost:11434")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "not-needed")
        self.max_retries = max_retries
        self.timeout = timeout

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """Send a chat completion request and return the text response."""
        start = time.monotonic()
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await litellm.acompletion(
                    model=self.model,
                    messages=messages,
                    api_base=self.base_url,
                    api_key=self.api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=self.timeout,
                )
                content = response.choices[0].message.content or ""
                elapsed = time.monotonic() - start
                logger.debug(
                    "LLM response in %.2fs (attempt %d, model=%s)",
                    elapsed, attempt, self.model,
                )
                return content
            except Exception:
                if attempt == self.max_retries:
                    raise
                logger.warning("LLM attempt %d/%d failed, retrying", attempt, self.max_retries)

        raise RuntimeError("LLM completion failed after all retries")

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        output_model: type[T],
        *,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> T:
        """Request a completion and parse the response as a Pydantic model.

        The system message instructs the LLM to return valid JSON matching
        the schema. Falls back to extracting JSON from markdown code fences.
        """
        schema_json = json.dumps(output_model.model_json_schema(), indent=2)
        schema_msg = {
            "role": "system",
            "content": (
                "You must respond with valid JSON only, matching this schema:\n"
                f"```json\n{schema_json}\n```\n"
                "Do not include any text outside the JSON object."
            ),
        }

        raw = await self.complete(
            [schema_msg] + messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            json_lines = []
            inside = False
            for line in lines:
                if line.strip().startswith("```") and not inside:
                    inside = True
                    continue
                if line.strip().startswith("```") and inside:
                    break
                if inside:
                    json_lines.append(line)
            cleaned = "\n".join(json_lines)

        return output_model.model_validate_json(cleaned)
