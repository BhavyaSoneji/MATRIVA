"""LangChain provider adapters for MATRIVA's grounded generation path.

The safety, retrieval, grounding, citation and post-check stages remain
independent Python functions; this module supplies the LangChain model and
prompt runnables used by the LCEL chain in ``app.rag.pipeline``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_groq import ChatGroq

from app.core.config import Settings, get_settings
from app.llm.groq_client import _build_messages, generate_from_packet, stream_from_packet
from app.rag.context_packet import ContextPacket

DEFAULT_TEMPERATURE = 0.2
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 3


class LangChainProviderError(RuntimeError):
    """Raised when the configured LangChain provider cannot be constructed."""


def packet_messages(context_packet: ContextPacket) -> list[dict[str, str]]:
    """Convert a MATRIVA context packet to ChatGroq-compatible messages.

    Message construction is deliberately the same helper used by the legacy
    client, so the system prompt, prompt-injection defense, multi-domain
    segmentation rules and external-web warning cannot drift between the
    LangChain and compatibility paths.
    """

    return _build_messages(context_packet)


def build_chat_model(settings: Settings | None = None) -> ChatGroq:
    """Build the production LangChain Groq chat model."""

    resolved = settings or get_settings()
    if not resolved.llm_api_key:
        raise LangChainProviderError("Groq API key not configured")
    try:
        return ChatGroq(
            model_name=resolved.llm_model,
            api_key=resolved.llm_api_key,
            temperature=DEFAULT_TEMPERATURE,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            max_retries=DEFAULT_MAX_RETRIES,
        )
    except Exception as exc:  # noqa: BLE001
        raise LangChainProviderError("failed to initialize ChatGroq") from exc


def build_generation_runnable(
    *,
    settings: Settings | None = None,
    client: Any | None = None,
    legacy_generator: Any = generate_from_packet,
) -> Runnable[Any, str]:
    """Return a LangChain runnable that maps a ``ContextPacket`` to text.

    Production uses ``ChatGroq``. An injected Groq-compatible client is kept
    as an explicit compatibility seam for deterministic unit tests; it is
    still executed inside the LangChain chain, so orchestration, safety
    short-circuiting and final validation remain identical.
    """

    if client is not None:
        return RunnableLambda(lambda packet: legacy_generator(packet, client=client))
    # Provider construction is lazy so an urgent/insufficient-evidence branch
    # can short-circuit without even instantiating a model client.
    lazy_model = RunnableLambda(lambda _messages: build_chat_model(settings))
    return RunnableLambda(packet_messages) | lazy_model | StrOutputParser()


def stream_generation(
    context_packet: ContextPacket,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
    legacy_streamer: Any = stream_from_packet,
) -> Iterator[str]:
    """Stream raw answer deltas through LangChain's model streaming API.

    As with blocking generation, an injected client uses the legacy stream
    helper only as a test seam; production streams through ``ChatGroq``.
    """

    if client is not None:
        yield from legacy_streamer(context_packet, client=client)
        return

    messages = packet_messages(context_packet)
    for chunk in build_chat_model(settings).stream(messages):
        text = getattr(chunk, "content", "")
        if isinstance(text, str) and text:
            yield text
        elif isinstance(text, list):
            # Content blocks are content, never instructions, and are only
            # flattened here after the provider has produced them.
            for block in text:
                if isinstance(block, str):
                    yield block
                elif isinstance(block, dict) and isinstance(block.get("text"), str):
                    yield block["text"]