"""Shared keyword-overlap scoring, used by Sprint 0's seed_qa.py and #6's
hybrid retrieval as the keyword component of "semantic vector search +
metadata filtering + keyword search where useful" (Section 12 Step 6).
"""

from __future__ import annotations

import re

_STOPWORDS = {
    "the", "a", "an", "is", "are", "what", "should", "for", "of", "in", "on",
    "to", "and", "or", "my", "me", "i", "do", "does", "can", "any", "with",
}


def tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOPWORDS}


def keyword_overlap_score(query: str, text: str) -> int:
    return len(tokenize(query) & tokenize(text))
