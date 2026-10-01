"""Query normalisation shared by the guard-rail matcher: case, Unicode form, punctuation, language by script."""

from __future__ import annotations

import re
import unicodedata

_APOSTROPHES = re.compile(r"['’`´]")
# Keep letters, digits and combining marks (Devanagari / Gujarati vowel signs are marks, not letters).
_PUNCT = re.compile(r"[^\w\s\u0900-\u097f\u0a80-\u0aff]", re.UNICODE)
_SPACES = re.compile(r"\s+")
_ELONGATION = re.compile(r"(.)\1{2,}")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = _APOSTROPHES.sub("", text)
    text = _ELONGATION.sub(r"\1\1", text)  # "painnnn" -> "painn"
    text = _PUNCT.sub(" ", text.replace("_", " "))
    return _SPACES.sub(" ", text).strip()


def tokens(text: str) -> list[str]:
    return normalize(text).split()


def script_language(text: str) -> str | None:
    """'hi' for Devanagari, 'gu' for Gujarati, else None (English or romanised)."""
    devanagari = sum(1 for ch in text if "ऀ" <= ch <= "ॿ")
    gujarati = sum(1 for ch in text if "઀" <= ch <= "૿")
    if gujarati > devanagari and gujarati:
        return "gu"
    if devanagari:
        return "hi"
    return None


def is_latin(term: str) -> bool:
    return all(ord(ch) < 0x0250 for ch in term if ch.isalpha())


def edit_distance_at_most_one(a: str, b: str) -> bool:
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diffs = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        if len(diffs) == 1:
            return True
        return len(diffs) == 2 and diffs[1] == diffs[0] + 1 and a[diffs[0]] == b[diffs[1]] and a[diffs[1]] == b[diffs[0]]
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    i = j = 0
    skipped = False
    while i < len(short) and j < len(long_):
        if short[i] == long_[j]:
            i += 1
            j += 1
        elif skipped:
            return False
        else:
            skipped = True
            j += 1
    return True
