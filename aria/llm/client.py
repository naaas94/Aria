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
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

litellm.drop_params = True

_PLACEHOLDER_API_KEYS = frozenset(
    {"", "not-needed", "not-needed-for-ollama"},
)

_FENCE_MAX_LAYERS = 5
_JSON_BRACE_PAIRS = {"{": "}", "[": "]"}
_JSON_CLOSERS = frozenset("}]")


def _strip_one_markdown_fence_layer(text: str) -> tuple[str, bool]:
    """Remove one outer ``` ... ``` block; handles consecutive opening fence lines.

    Returns (stripped_content, True) if a layer was removed, else (text, False).
    """
    t = text.strip()
    if not t.startswith("```"):
        return text, False
    lines = t.split("\n")
    if len(lines) < 2:
        return "\n".join(lines[1:]).strip() if len(lines) == 1 else t, True
    rest = lines[1:]
    while rest and rest[0].strip().startswith("```"):
        rest = rest[1:]
    body: list[str] = []
    for line in rest:
        if line.strip() == "```":
            break
        body.append(line)
    inner = "\n".join(body).strip()
    return inner, True


def _strip_markdown_code_fences(text: str, *, max_layers: int = _FENCE_MAX_LAYERS) -> str:
    """Repeatedly strip outer markdown code fences (models sometimes nest them)."""
    t = text.strip()
    for _ in range(max_layers):
        new_t, changed = _strip_one_markdown_fence_layer(t)
        if not changed:
            break
        t = new_t.strip()
    return t


def _first_balanced_json_slice(s: str) -> str | None:
    """Find the first JSON object or array substring with balanced braces (string-aware)."""
    start: int | None = None
    for i, c in enumerate(s):
        if c in "{[":
            start = i
            break
    if start is None:
        return None
    stack: list[str] = []
    in_str = False
    escape = False
    i = start
    while i < len(s):
        c = s[i]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            i += 1
            continue
        if c in "{[":
            stack.append(c)
        elif c in _JSON_CLOSERS:
            if not stack:
                return None
            op = stack.pop()
            expected = _JSON_BRACE_PAIRS[op]
            if c != expected:
                return None
            if not stack:
                return s[start : i + 1]
        i += 1
    return None


def _parse_llm_json_payload(raw: str, output_model: type[T]) -> T:
    """Strip fences, parse JSON, then fall back to extracting a balanced `{...}` / `[...]` slice."""
    cleaned = _strip_markdown_code_fences(raw)
    try:
        return output_model.model_validate_json(cleaned)
    except ValidationError:
        slice_json = _first_balanced_json_slice(cleaned)
        if slice_json and slice_json != cleaned:
            return output_model.model_validate_json(slice_json)
        slice_raw = _first_balanced_json_slice(raw.strip())
        if slice_raw:
            return output_model.model_validate_json(slice_raw)
        raise


def _looks_like_local_llm(model: str, base_url: str) -> bool:
    """Heuristic: Ollama id or API base on loopback does not need a cloud API key."""
    m = model.strip().lower()
    if m.startswith("ollama/"):
        return True
    u = base_url.strip().lower()
    return "localhost" in u or "127.0.0.1" in u


def _require_non_placeholder_api_key(model: str, base_url: str, api_key: str) -> None:
    if _looks_like_local_llm(model, base_url):
        return
    key = (api_key or "").strip().lower()
    if key in _PLACEHOLDER_API_KEYS or not (api_key or "").strip():
        raise ValueError(
            "LLM_API_KEY must be set to a real provider key when using a non-local model "
            f"(model={model!r}, LLM_BASE_URL={base_url!r}). "
            "For Ollama, use a model id prefixed with 'ollama/' and a local LLM_BASE_URL."
        )


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
        _require_non_placeholder_api_key(self.model, self.base_url, self.api_key)

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
            except Exception as exc:
                if attempt == self.max_retries:
                    if isinstance(exc, TimeoutError):
                        logger.error(
                            "LLM completion timed out (per-attempt timeout=%ss, model=%s)",
                            self.timeout,
                            self.model,
                        )
                    else:
                        logger.error(
                            "LLM completion failed after %d attempts (%s): %s",
                            self.max_retries,
                            type(exc).__name__,
                            exc,
                        )
                    raise
                logger.warning(
                    "LLM attempt %d/%d failed (%s), retrying",
                    attempt,
                    self.max_retries,
                    type(exc).__name__,
                )

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

        Strips nested markdown code fences, parses JSON, then (if needed) extracts
        the first balanced ``{...}`` or ``[...]`` slice to tolerate leading prose
        or malformed wrappers. Trailing text after valid JSON is not accepted if
        the slice parse fails.
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

        base_messages = [schema_msg] + messages
        raw = await self.complete(
            base_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        try:
            return _parse_llm_json_payload(raw, output_model)
        except ValidationError as first_exc:
            repair_messages = [
                schema_msg,
                {"role": "assistant", "content": raw},
                {
                    "role": "user",
                    "content": (
                        "That output was not valid JSON for the required schema. "
                        "Reply with one JSON object only — no markdown fences, no commentary."
                    ),
                },
            ]
            raw2 = await self.complete(
                repair_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            try:
                return _parse_llm_json_payload(raw2, output_model)
            except ValidationError:
                raise first_exc from None
