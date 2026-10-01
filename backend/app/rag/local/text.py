"""Text processing for the local retriever: folding, tokenising, stemming and character n-grams.

Everything here is deterministic and dependency-free so the whole RAG pipeline runs offline.
Two things matter for this corpus in particular:

* Sanskrit transliteration is written inconsistently ("garbha"/"garbh", "kşīra"/"ksira"), so text is
  diacritic-folded before anything else.
* The book comes from OCR, so single characters are often wrong ("wornan", "fetns"). Word tokens
  would miss those; character n-grams still match most of the word, which is why the retriever
  scores both.
"""

from __future__ import annotations

import re
import unicodedata

STOPWORDS = frozenset(
    """a about above after again all also am an and any are as at be because been before being below
    between both but by can could did do does doing down during each few for from further had has have
    having he her here hers him his how i if in into is it its just me more most my no nor not of off on
    once only or other our out over own same she should so some such than that the their theirs them
    then there these they this those through to too under until up very was we were what when where which
    while who whom why will with would you your yours tell please give say may might must shall
    much many long often take taking get got use using need needs want make makes work works know okay ok good best""".split()
)

# Words users reach for that the corpus spells differently (kept small and corpus-grounded, like
# retrieval._SYNONYMS). Applied to BOTH queries and passages so the two always agree.
QUERY_SYNONYMS = {
    "prenatal": "antenatal", "checkup": "visit", "checkups": "visit", "appointment": "visit",
    "appointments": "visit", "physician": "doctor", "obstetrician": "doctor", "gynecologist": "doctor",
    "gynaecologist": "doctor", "eat": "food", "eating": "food", "diet": "food", "meal": "food",
    "meals": "food", "foods": "food", "fetal": "fetus", "foetal": "fetus", "foetus": "fetus",
    "baby": "fetus", "tummy": "abdomen", "stomach": "abdomen", "safe": "safe", "unsafe": "unsafe",
    "hemoglobin": "haemoglobin", "ayurvedic": "ayurveda", "ayurved": "ayurveda", "ayurvedik": "ayurveda", "women": "woman", "mothers": "mother", "babies": "fetus", "anemia": "anaemia", "labor": "labour", "esophagus": "oesophagus",
}

_WORD = re.compile(r"[a-z0-9]+")


def fold(text: str) -> str:
    """Lower-case and strip diacritics: 'Kṣīra' -> 'ksira', 'Śatāvarī' -> 'satavari'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def stem(word: str) -> str:
    """A deliberately light suffix stripper (plurals, -ing, -ed, -ly, -ion, -ness...).

    Over-stemming is harmless here because both query and corpus go through the same function.
    """
    w = word
    if len(w) <= 3:
        return w
    for suffix, minimum in (
        ("ies", 3), ("ing", 4), ("edly", 4), ("ness", 4), ("ment", 4), ("ation", 4), ("tion", 4), ("sion", 4),
        ("ity", 4), ("ally", 4), ("ly", 4), ("ed", 4), ("es", 4), ("s", 4), ("al", 4), ("ic", 4),
    ):
        if suffix == "ed" and w.endswith("eed"):
            continue  # "feed" / "breastfeed" are not past tenses
        if suffix == "s" and w.endswith(("ss", "us", "is")):
            continue  # "illness", "uterus", "analysis"
        if w.endswith(suffix) and len(w) - len(suffix) >= minimum:
            w = w[: -len(suffix)]
            if suffix == "ies":
                w += "y"
            break
    if len(w) > 4 and w[-1] == w[-2] and w[-1] not in "aeiouls":  # "running" -> "runn" -> "run"
        w = w[:-1]
    return w


def words(text: str) -> list[str]:
    """Folded alphanumeric words in order (stopwords kept)."""
    return _WORD.findall(fold(text))


def tokens(text: str) -> list[str]:
    """Stemmed content tokens, after synonym normalisation."""
    out: list[str] = []
    for w in words(text):
        w = QUERY_SYNONYMS.get(w, w)
        if w in STOPWORDS or len(w) < 2:
            continue
        out.append(stem(w))
    return out


def char_ngrams(text: str, sizes: tuple[int, ...] = (3, 4)) -> list[str]:
    """Character n-grams over each word, padded with ^ and $ so word edges count."""
    grams: list[str] = []
    for w in words(text):
        if w in STOPWORDS or len(w) < 3:
            continue
        padded = f"^{w}$"
        for n in sizes:
            if len(padded) >= n:
                grams.extend(padded[i : i + n] for i in range(len(padded) - n + 1))
    return grams


_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
_ABBREV = ("i.e", "e.g", "viz", "cf", "etc", "dr", "no", "fig", "vol", "ch", "sl", "vs")


def sentences(text: str) -> list[str]:
    """Split into sentences, keeping common abbreviations ('i.e.', 'Dr.') intact."""
    out: list[str] = []
    for para in re.split(r"\n{2,}", text):
        buf = ""
        for piece in _SENTENCE_BREAK.split(" ".join(para.split())):
            buf = f"{buf} {piece}".strip() if buf else piece
            last = buf.rsplit(" ", 1)[-1].lower().rstrip(".")
            if last in _ABBREV:
                continue  # the break was inside an abbreviation; keep accumulating
            if len(buf.split()) >= 4:
                out.append(buf)
            buf = ""
        if buf and len(buf.split()) >= 4:
            out.append(buf)
    return out


_TRAILING_NUMBER = re.compile(r"\s\d{1,3}\.?$")
_DEVANAGARI = re.compile(r"[\u0900-\u097f]")


def is_prose(sentence: str, *, min_words: int = 6) -> bool:
    """False for OCR debris, headings and list fragments: too short, mixed with Devanagari, ending in a stray
    page/list number, digit-saturated, or with no function words. Dosages ("30-60 mg") are fine."""
    ws = words(sentence)
    if len(ws) < min_words or _DEVANAGARI.search(sentence) or _TRAILING_NUMBER.search(sentence.strip()):
        return False
    letters = sum(ch.isalpha() for ch in sentence)
    digits = sum(ch.isdigit() for ch in sentence)
    if digits > 0.15 * max(letters + digits, 1):
        return False
    return sum(w in STOPWORDS for w in ws) / len(ws) >= 0.15
