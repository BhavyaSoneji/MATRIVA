"""Groq LLM integration for source-grounded generation (issue #9).

Full version of what Sprint 0's seed_qa.py did minimally: a reusable client
wrapper with retry/timeout handling, taking a #8 ContextPacket as input and
enforcing the Section 58 source-grounded system prompt. No personalization
here -- Phase 4 is grounded QA only, per spec; personalization is #11.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from typing import Any, cast

try:
    from groq import APIConnectionError, APIStatusError, APITimeoutError, Groq
except ImportError:  # optional provider; local/demo mode uses a grounded fallback
    class APIConnectionError(Exception):  # type: ignore[no-redef]
        pass

    class APIStatusError(Exception):  # type: ignore[no-redef]
        pass

    class APITimeoutError(Exception):  # type: ignore[no-redef]
        pass

    class Groq:  # type: ignore[no-redef]
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("Groq client is not installed; install the optional provider dependencies")

from app.llm.prompts import SOURCE_GROUNDED_SYSTEM_PROMPT
from app.rag.context_packet import ContextPacket
from app.rag.multi_domain import MULTI_DOMAIN_PROMPT_ADDENDUM, requires_segmentation
from app.safety.prompt_injection import INJECTION_DEFENSE_ADDENDUM

WEB_SEARCH_PROMPT_ADDENDUM = """
Some of the evidence below is under "EXTERNAL WEB SOURCES (UNVERIFIED)" rather than
RETRIEVED SOURCES. That content comes from a live web search, not the reviewed local
knowledge base -- treat it as lower-confidence supporting context only. When you use it,
cite it using its own [webN] marker (never merge it into or present it with the same
confidence as a RETRIEVED SOURCES citation), and say plainly that it comes from an
external, unverified web source rather than a reviewed medical guideline."""

DEFAULT_MODEL = "openai/gpt-oss-120b"
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


def _build_messages(context_packet: ContextPacket) -> list[dict[str, str]]:
    """Shared system/user message construction for both the blocking
    (`generate_from_packet`) and streaming (`stream_from_packet`) generation
    paths -- kept in one place so the two never drift (e.g. one adding the
    web-search addendum and the other forgetting to)."""
    # Section 44: always-on defense -- retrieved evidence is untrusted data,
    # never instructions, regardless of what it contains.
    system_prompt = SOURCE_GROUNDED_SYSTEM_PROMPT + "\n" + INJECTION_DEFENSE_ADDENDUM
    if requires_segmentation(context_packet.evidence_summary.domains):
        # Section 31: retrieved evidence spans AYURVEDA + another domain --
        # enforce clearly separated MODERN/TRADITIONAL/EVIDENCE STATUS sections.
        system_prompt = system_prompt + "\n" + MULTI_DOMAIN_PROMPT_ADDENDUM
    if context_packet.web_sources:
        # Live web search (Tavily) results are present -- reinforce, at the
        # instruction level, the same separation the packet already builds
        # structurally (see ContextPacket.to_prompt_text).
        system_prompt = system_prompt + "\n" + WEB_SEARCH_PROMPT_ADDENDUM

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": context_packet.to_prompt_text()},
    ]


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

    messages = _build_messages(context_packet)

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,  # type: ignore[arg-type]  # plain dicts match the SDK's TypedDict shape at runtime
                temperature=temperature,
            )
            if not completion.choices:
                raise GenerationError("Groq response had no choices (empty response)")
            content = completion.choices[0].message.content
            if content is None:
                raise GenerationError("Groq response had no content (empty choice)")
            return content
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


def stream_from_packet(
    context_packet: ContextPacket,
    *,
    client: Groq | None = None,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    temperature: float = 0.2,
) -> Iterator[str]:
    """Streaming counterpart to `generate_from_packet` (POST /chat/stream).

    Same system prompt, same untrusted-data framing, same injection defense,
    same web-search addendum -- built from the identical `_build_messages`
    helper, so a streamed answer is grounded exactly the same way a blocking
    one is. The ONLY difference from `generate_from_packet` is `stream=True`
    on the Groq call and yielding each text delta as it arrives instead of
    waiting for and returning the complete string.

    Deliberately no retry-with-backoff here (unlike `generate_from_packet`):
    once tokens have already been yielded to a caller (which, per
    app.rag.pipeline.answer_query_stream, is a caller that is itself already
    forwarding them to an open HTTP response), silently retrying and
    re-yielding a second attempt's tokens on top would duplicate/garble
    output the client already rendered. A single attempt fails fast; the
    caller (see answer_query_stream) is responsible for turning a failure
    partway through a stream into a safe, explicit final answer -- never
    silently swallowed.
    """
    if client is None:
        client = Groq(api_key=_resolve_api_key(api_key), timeout=timeout)

    messages = _build_messages(context_packet)

    # cast: the real SDK's overloaded return type (ChatCompletion for
    # stream=False vs Stream[ChatCompletionChunk] for stream=True) doesn't
    # narrow cleanly against our plain-dict `messages`/injectable-fake
    # `client` (same reason generate_from_packet above needs its own
    # `type: ignore[arg-type]`) -- callers only ever pass either the real
    # Groq SDK with stream=True (an iterator of chunks) or a test fake with
    # the same shape (see tests/test_groq_client.py's streaming cases).
    stream = cast(
        "Iterator[Any]",
        client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            stream=True,
        ),
    )
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
