"""Classical authorities cited in the Ayurveda text (Caraka, Susruta, Vagbhata ...), as the OCR spells them.

Kept in step with ingestion/pipelines/book_structure.py (a test enforces it). Used to answer "what does Caraka say
about X?": passages that name the authority are preferred, and sentences naming it are preferred inside them.
"""

from __future__ import annotations

import re

from app.rag.local.text import fold

AUTHORITIES: dict[str, tuple[str, ...]] = {
    "Caraka": ("caraka", "carak", "charaka"),
    "Susruta": ("susruta", "sugruta", "sueruta", "sushruta", "susrut"),
    "Vagbhata": ("vagbhata", "vagbhat", "vaabhata"),
    "Kasyapa": ("kasyapa", "kagyapa", "kasyap", "kashyapa", "kaeyapa"),
    "Harita": ("harita",),
    "Bhela": ("bhela",),
    "Sarngadhara": ("sarngadhara", "sarngadhar"),
    "Madhava": ("madhava", "madhavakara"),
    "Bhavamisra": ("bhavamisra", "bhavaprakasa", "bhavaprakash"),
    "Vangasena": ("vangasena", "vangsena"),
    "Dalhana": ("dalhana", "dalhan"),
    "Cakrapani": ("cakrapani", "chakrapani", "cakrapan"),
    "Indu": ("indu",),
    "Arunadatta": ("arunadatta", "aruuadatta", "arunadat"),
    "Videha (Nimi)": ("videha", "nimi"),
    "Yogaratnakara": ("yogaratnakara", "yogaratnakar"),
}
_PATTERNS = {
    name: re.compile(r"\b(?:" + "|".join(re.escape(fold(v)) for v in sorted(variants, key=len, reverse=True)) + r")")
    for name, variants in AUTHORITIES.items()
}


def detect(text: str) -> dict[str, int]:
    """{authority: mentions} in `text`."""
    folded = fold(text)
    out = {}
    for name, pattern in _PATTERNS.items():
        n = len(pattern.findall(folded))
        if n:
            out[name] = n
    return out
