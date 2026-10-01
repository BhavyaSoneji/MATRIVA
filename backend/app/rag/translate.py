"""Turn a Hindi / Hinglish / Gujarati question into an English retrieval query.

The reviewed knowledge base is in English, and keyword retrieval cannot match Devanagari or
Gujarati script against it. Two steps, cheapest first:

1. A small glossary of pregnancy words (deterministic, offline, always available).
2. When an LLM key is configured, a one-shot translation. That result wins over the glossary
   because it keeps the question's meaning; the glossary is the safety net when it fails.

The translated text is ONLY used to search -- it is never shown to the user or used for the safety
check (which runs on the user's original words, in every language).
"""

from __future__ import annotations

import logging
import unicodedata
from collections.abc import Callable

logger = logging.getLogger("matriva.translate")

# substring (NFKC, lower-cased) -> English retrieval words
GLOSSARY: dict[str, str] = {
    # --- Hindi (Devanagari) ---
    "गर्भावस्था": "pregnancy", "प्रेगनेंसी": "pregnancy", "तिमाही": "trimester", "पहली तिमाही": "first trimester",
    "दूसरी तिमाही": "second trimester", "तीसरी तिमाही": "third trimester",
    "खाना": "food diet", "खाने": "food diet", "भोजन": "food diet", "आहार": "food diet", "पोषण": "nutrition",
    "आयरन": "iron", "कैल्शियम": "calcium", "फोलिक": "folic acid", "विटामिन": "vitamin", "प्रोटीन": "protein",
    "दूध": "milk", "दही": "curd yogurt", "दाल": "lentils dal", "रागी": "ragi", "पालक": "spinach", "केला": "banana",
    "पपीता": "papaya", "कैफीन": "caffeine", "चाय": "tea", "कॉफी": "coffee", "घी": "ghee",
    "योग": "yoga", "व्यायाम": "exercise", "सैर": "walk exercise", "नींद": "sleep", "सोने": "sleep position", "तनाव": "stress",
    "उल्टी": "vomiting nausea morning sickness", "मतली": "nausea morning sickness", "पीठ दर्द": "back pain",
    "कब्ज": "constipation", "एनीमिया": "anaemia", "खून की कमी": "anaemia", "मधुमेह": "gestational diabetes",
    "शुगर": "diabetes", "ब्लड प्रेशर": "blood pressure", "टीका": "vaccine", "टीकाकरण": "vaccine",
    "चेकअप": "antenatal checkup visit", "जांच": "antenatal checkup screening", "एंटेनेटल": "antenatal",
    "अल्ट्रासाउंड": "ultrasound scan", "डिलीवरी": "labour delivery", "प्रसव": "labour delivery",
    "स्तनपान": "breastfeeding", "आयुर्वेद": "ayurveda", "शेड्यूल": "schedule", "योजना": "scheme",
    "हलचल": "baby movement", "बच्चे की": "baby", "बच्चा": "baby",
    # --- Hinglish (Roman) ---
    "khana": "food diet", "khane": "food diet", "aahar": "food diet", "poshan": "nutrition", "doodh": "milk",
    "dahi": "curd yogurt", "dal": "lentils dal", "chai": "tea", "neend": "sleep", "ulti": "vomiting nausea",
    "kabz": "constipation", "tika": "vaccine", "jaanch": "antenatal checkup", "checkup": "antenatal checkup",
    "prasav": "labour delivery", "stanpan": "breastfeeding", "vyayam": "exercise", "garbhavastha": "pregnancy",
    "pregnancy": "pregnancy", "ayurved": "ayurveda",
    # --- Gujarati ---
    "ગર્ભાવસ્થા": "pregnancy", "ખાવું": "food diet", "ખોરાક": "food diet", "આહાર": "food diet", "દૂધ": "milk",
    "દહીં": "curd yogurt", "દાળ": "lentils dal", "યોગ": "yoga", "કસરત": "exercise", "ઊંઘ": "sleep",
    "ઉલટી": "vomiting nausea morning sickness", "રસી": "vaccine", "સ્તનપાન": "breastfeeding",
    "આયુર્વેદ": "ayurveda", "આયર્ન": "iron", "કેલ્શિયમ": "calcium", "વિટામિન": "vitamin", "ચા": "tea", "કોફી": "coffee",
    "તપાસ": "antenatal checkup",
}
_NORMALISED = {unicodedata.normalize("NFKC", k).lower(): v for k, v in GLOSSARY.items()}
_MAX_QUERY_CHARS = 300


def _is_ascii(text: str) -> bool:
    return all(ord(ch) < 128 for ch in text)


def glossary_translate(text: str) -> str | None:
    """English words for every glossary term found in `text`, or None if none matched.

    Longest terms are matched first so "पहली तिमाही" wins over "तिमाही".
    """
    haystack = unicodedata.normalize("NFKC", text).lower()
    found: list[str] = []
    for term in sorted(_NORMALISED, key=len, reverse=True):
        if term in haystack:
            haystack = haystack.replace(term, " ")
            for word in _NORMALISED[term].split():
                if word not in found:
                    found.append(word)
    return " ".join(found) if found else None


def llm_translate(text: str) -> str | None:
    """One-shot LLM translation to English; None when no key is configured or the call fails."""
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.llm_api_key:
        return None
    try:
        from groq import Groq

        completion = Groq(api_key=settings.llm_api_key, timeout=8.0).chat.completions.create(
            model=settings.llm_model,
            temperature=0,
            max_tokens=120,
            messages=[
                {"role": "system", "content": "Translate the user's pregnancy question into plain English. Output only the English question, nothing else. Do not answer it."},
                {"role": "user", "content": text[:_MAX_QUERY_CHARS]},
            ],
        )
        out = (completion.choices[0].message.content or "").strip()
        return out[:_MAX_QUERY_CHARS] or None
    except Exception:  # noqa: BLE001 - translation is best-effort
        logger.exception("llm translation failed; falling back to glossary")
        return None


def to_english_query(
    text: str,
    *,
    language: str | None = None,
    translator: Callable[[str], str | None] = llm_translate,
) -> str:
    """English retrieval query for `text`; unchanged for ordinary English input.

    Applies when the text contains non-Latin script, or the user chose Hindi/Gujarati and typed
    in Roman letters ("Hinglish"). Roman-script input only uses the glossary (no LLM call).
    """
    if _is_ascii(text) and language not in {"hi", "gu"}:
        return text
    if not _is_ascii(text):
        translated = translator(text)
        if translated:
            return translated
    return glossary_translate(text) or text
