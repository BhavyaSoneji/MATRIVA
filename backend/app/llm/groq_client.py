"""Groq LLM integration for source-grounded generation (issue #9).

Full version of what Sprint 0's seed_qa.py did minimally: a reusable client
wrapper with retry/timeout handling, taking a #8 ContextPacket as input and
enforcing the Section 58 source-grounded system prompt. No personalization
here -- Phase 4 is grounded QA only, per spec; personalization is #11.
"""

from __future__ import annotations

import os
import time

from groq import APIConnectionError, APIStatusError, APITimeoutError, Groq

from app.llm.prompts import SOURCE_GROUNDED_SYSTEM_PROMPT
from app.rag.context_packet import ContextPacket

DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 1.0

_RETRYABLE_ERRORS = (APIConnectionError, APITimeoutError)


class GenerationError(RuntimeError):
    """Raised when generation fails after retries, or on a non-retryable API error."""


def _resolve_api_key(api_key: str | None) -> str:
    key = api_key or os.environ.get("LLM_API_KEY") or os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("Groq API key not configured (set LLM_API_KEY or GROQ_API_KEY)")
    return key


def generate_from_packet(
    context_packet: ContextPacket,
    *,
    client: Groq | None = None,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    temperature: float = 0.2,
) -> str:
    """Generate a source-grounded response from a #8 ContextPacket.

    Retries on transient connection/timeout errors with exponential backoff;
    fails immediately (no retry) on a non-retryable API error (auth, bad
    request, rate limit, etc.) since retrying those wastes time without a
    chance of success.
    """
    if client is None:
        client = Groq(api_key=_resolve_api_key(api_key), timeout=timeout)

    messages = [
        {"role": "system", "content": SOURCE_GROUNDED_SYSTEM_PROMPT},
        {"role": "user", "content": context_packet.to_prompt_text()},
    ]

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            completion = client.chat.completions.create(
                model=model, messages=messages, temperature=temperature
            )
            return completion.choices[0].message.content
        except _RETRYABLE_ERRORS as exc:
            last_error = exc
            if attempt < max_retries - 1:
                time.sleep(RETRY_BACKOFF_SECONDS * (2**attempt))
                continue
        except APIStatusError as exc:
            raise GenerationError(f"Groq API error (non-retryable): {exc}") from exc

    raise GenerationError(
        f"Groq generation failed after {max_retries} attempts: {last_error}"
    ) from last_error
