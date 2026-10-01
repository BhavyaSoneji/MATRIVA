"""Resolve short follow-up questions against the conversation so retrieval has something to search.

"What about ragi?" or "is it safe?" retrieve nothing on their own: the topic lives in the
previous turn. This deterministic helper (no LLM call, so it cannot add facts) prepends the
previous user question when the new one looks like a follow-up. The SAFETY pre-check always
runs on the user's original words, never on this expanded text.
"""

from __future__ import annotations

import re

from app.rag.retrieval import tokenize

_FOLLOWUP_OPENERS = (
    "what about", "how about", "and ", "also ", "is it", "is that", "is this", "are they", "are those",
    "can i", "can you", "why", "how much", "how many", "how often", "how long", "what if", "does it", "do they",
)
_PRONOUN_RE = re.compile(r"\b(it|that|this|they|them|those|these|there|same)\b", re.IGNORECASE)
_MAX_PREVIOUS_CHARS = 300
_MIN_NEW_TOKENS = 3  # fewer meaningful words than this -> almost certainly a follow-up


def looks_like_followup(message: str) -> bool:
    text = message.strip().lower()
    if len(tokenize(text)) < _MIN_NEW_TOKENS:
        return True
    if text.startswith(_FOLLOWUP_OPENERS) and len(text.split()) <= 8:
        return True
    return bool(_PRONOUN_RE.search(text)) and len(text.split()) <= 8


def resolve_followup(message: str, previous_user_messages: list[str]) -> str:
    """Return `message` unchanged unless it is a follow-up and a previous question exists."""
    if not previous_user_messages or not looks_like_followup(message):
        return message
    previous = previous_user_messages[0].strip()[:_MAX_PREVIOUS_CHARS]
    if not previous or previous.lower() == message.strip().lower():
        return message
    return f"{previous} {message}"
