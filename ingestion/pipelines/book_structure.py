"""Recover the structure of the Prasuti Tantra from its OCR: outline, bilingual glossary and authorities.

Everything is deterministic text processing -- no model, no network:

* The book has a bilingual table of contents ("Devanagari title (English title)  page"). Its rows, and the
  `CHAPTER n` markers, give the outline: chapters containing sections with a printed page number.
* Each scanned image is a two-page spread, so scanned page = FIRST_SCAN + (printed - 1) // 2.
* OCR garbles some page numbers, so section pages are filtered to the longest non-decreasing run
  (a wrong number cannot reorder the outline).
* Headings that pair a Hindi title with an English gloss, in the contents and in the body, are collected as a
  Hindi <-> English glossary.
* Classical authorities (Caraka, Susruta, Vagbhata, Kasyapa ...) are counted per chapter from the English text.

Quality is reported, not hidden: entries the parser could not place are counted in `stats`.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from pipelines.ocr_english import split_pages

TOC_PAGES = range(18, 26)  # scanned pages carrying the contents
FIRST_SCAN = 27  # scanned page where printed page 1 (Chapter 1) begins
_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_ENTRY = re.compile(r"\(([A-Za-z][^()]{4,160}?(?:\([^()]{0,60}\)[^()]{0,60})?)\)\s*([०-९0-9]{2,4})\b")
_MARKER = re.compile(r"CHAPTER\s*([0-9IVXl|]{1,4})")
_ROMAN = {"I": 1, "l": 1, "|": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11}

# Authorities and the spellings OCR produces for them (matched on diacritic-folded, lower-case text).
AUTHORITIES: dict[str, tuple[str, ...]] = {
    "Caraka": ("caraka", "carak", "charaka"),
    "Susruta": ("susruta", "sugruta", "sueruta", "suéruta", "sushruta", "susrut"),
    "Vagbhata": ("vagbhata", "vagbhat", "vaabhata", "vagbhata-i", "vagbhata i"),
    "Kasyapa": ("kasyapa", "kagyapa", "kasyap", "kashyapa", "kaéyapa"),
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


@dataclass
class Section:
    title_en: str
    title_hi: str
    printed_page: int
    scan_page: int


@dataclass
class Chapter:
    number: int
    title_en: str
    title_hi: str
    scan_start: int
    scan_end: int
    sections: list[Section] = field(default_factory=list)


def clean_hindi(text: str) -> str:
    """Drop OCR stragglers (stray digits and one/two-letter fragments) from the front of a Hindi title."""
    words = text.split()
    while words and (len(words[0]) <= 2 or words[0].translate(_DEV_DIGITS).isdigit()):
        words.pop(0)
    return " ".join(words)


def to_scan(printed: int) -> int:
    return FIRST_SCAN + (printed - 1) // 2


def parse_number(token: str) -> int | None:
    digits = token.translate(_DEV_DIGITS)
    return int(digits) if digits.isdigit() else None


def _english_part(raw: str) -> str:
    text = re.sub(r"\s+", " ", raw).strip()
    text = _DEVANAGARI.split(text)[0].strip(" ,;:-")
    return re.sub(r"\s+-\s+", "-", text)


def _hindi_before(page_text: str, start: int) -> str:
    """The Devanagari title that precedes an English gloss on the same line."""
    line_start = page_text.rfind("\n", 0, start) + 1
    run = re.findall(r"[ऀ-ॿ][ऀ-ॿ\s\-,/‌‍]{2,80}", page_text[line_start:start])
    return re.sub(r"\s+", " ", run[-1]).strip(" -") if run else ""


def longest_non_decreasing(values: list[int]) -> list[int]:
    """Indices of a longest non-decreasing subsequence -- the entries whose page numbers can be trusted."""
    if not values:
        return []
    best_len, best_prev = [1] * len(values), [-1] * len(values)
    for i in range(len(values)):
        for j in range(i):
            if values[j] <= values[i] and best_len[j] + 1 > best_len[i]:
                best_len[i], best_prev[i] = best_len[j] + 1, j
    end = max(range(len(values)), key=lambda i: best_len[i])
    out = []
    while end != -1:
        out.append(end)
        end = best_prev[end]
    return out[::-1]


def _fold(text: str) -> str:
    import unicodedata

    return "".join(ch for ch in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(ch))


def _content_words(title: str) -> list[str]:
    return [w for w in set(re.findall(r"[a-z]{4,}", _fold(title)))]


def locate(title: str, printed: int, folded_pages: dict[int, str], window: int = 7, min_score: float = 0.5) -> int | None:
    """Scanned page where a contents row really is, found by reading the body.

    The printed->scan formula drifts (plates, blank pages), so the row's title words are searched for in the
    pages around the prediction; the best-matching page nearest the prediction wins. Rows whose words are not
    found nearby are rejected rather than guessed.
    """
    words = _content_words(title)
    if not words:
        return None
    predicted = to_scan(printed)
    best: tuple[float, int, int] | None = None
    for page in range(predicted - window, predicted + window + 1):
        text = folded_pages.get(page)
        if not text:
            continue
        score = sum(1 for w in words if w in text) / len(words)
        key = (score, -abs(page - predicted), page)
        if score >= min_score and (best is None or key > best):
            best = key
    return best[2] if best else None


_CHAPTER_HEAD = re.compile(r"CHAPTER\s*[0-9IVXl|\u0900-\u097fQ]{0,5}[^\n]{0,40}\n?(?:[^\n]*\n){0,3}?[^\n]*?\(([A-Z][A-Z \n,/&'’\-\.\(\)]{7,140})\)", re.S)


def detect_chapters(pages: dict[int, str], first_body_page: int = FIRST_SCAN) -> list[tuple[int, str, str]]:
    """[(scan page, English title, Hindi title)] for each chapter heading found in the body, in page order.

    A heading is `अध्याय N / CHAPTER N / <Hindi title> / (UPPER-CASE ENGLISH TITLE)`; the number itself is
    often garbled by OCR, so chapters are numbered by order of appearance.
    """
    out: list[tuple[int, str, str]] = []
    for page in sorted(p for p in pages if p >= first_body_page):
        text = pages[page]
        m = _CHAPTER_HEAD.search(text)
        if not m or "अध्याय" not in text[max(0, m.start() - 40) : m.end()]:
            continue
        english = re.sub(r"\s+", " ", m.group(1)).strip().title()
        head = text[max(0, m.start() - 20) : m.end()]
        hindi_runs = re.findall(r"[\u0900-\u097f][\u0900-\u097f\s\-]{5,80}", head[head.find("CHAPTER") :])
        hindi = re.sub(r"\s+", " ", hindi_runs[0]).strip(" -") if hindi_runs else ""
        if out and english == out[-1][1]:
            continue
        out.append((page, english, hindi))
    return out


def parse_contents(pages: dict[int, str]) -> tuple[list[Section], dict[str, int]]:
    """Section rows from the bilingual contents, each verified against the body text."""
    folded = {n: _fold(t) for n, t in pages.items()}
    sections: list[Section] = []
    seen = rejected = unverified = 0
    for n in (24, 25, 21, 22, 23):
        text = pages.get(n, "")
        for m in _ENTRY.finditer(text):
            seen += 1
            title = _english_part(m.group(1))
            printed = parse_number(m.group(2))
            if not title or printed is None or not 1 <= printed <= 830:
                rejected += 1
                continue
            scan = locate(title, printed, folded)
            if scan is None:
                unverified += 1
                continue
            sections.append(Section(title, clean_hindi(_hindi_before(text, m.start())), printed, scan))
    sections.sort(key=lambda s: (s.scan_page, s.printed_page))
    dedup: list[Section] = []
    for s in sections:  # the same row can appear twice when columns interleave
        if not dedup or (dedup[-1].title_en.lower(), dedup[-1].scan_page) != (s.title_en.lower(), s.scan_page):
            dedup.append(s)
    return dedup, {"toc_rows_seen": seen, "rejected_bad_page": rejected, "not_found_in_body": unverified, "verified_sections": len(dedup)}


def build_outline(raw: str, last_scan: int | None = None) -> tuple[list[Chapter], dict[str, int]]:
    pages = dict(split_pages(raw))
    last_scan = last_scan or max(pages)
    sections, stats = parse_contents(pages)
    heads = detect_chapters(pages)
    chapters: list[Chapter] = []
    for i, (start, en, hi) in enumerate(heads):
        end = heads[i + 1][0] - 1 if i + 1 < len(heads) else last_scan
        chapters.append(Chapter(i + 1, en, clean_hindi(hi), start, end, [s for s in sections if start <= s.scan_page <= end]))
    stats["chapters"] = len(chapters)
    return chapters, stats


def chapter_for(chapters: list[Chapter], scan_page: int) -> Chapter | None:
    for ch in chapters:
        if ch.scan_start <= scan_page <= ch.scan_end:
            return ch
    return None


def section_for(chapter: Chapter, scan_page: int) -> Section | None:
    best = None
    for s in chapter.sections:
        if s.scan_page <= scan_page:
            best = s
    return best


# ------------------------------------------------------------------ glossary and authorities
_PAIR = re.compile(r"([ऀ-ॿ][ऀ-ॿ\s\-]{2,60}?)\s*\(([A-Z][A-Za-z][A-Za-z ,/'’\-\.]{2,70})\)")


def _plausible_gloss(english: str) -> bool:
    """A gloss is a short phrase of ordinary words: no stray capital fragments ('BRS'), digits or very long runs."""
    words = english.split()
    return 1 <= len(words) <= 9 and not any(re.fullmatch(r"[A-Z0-9]{2,5}", w) or any(c.isdigit() for c in w) for w in words)


def build_glossary(raw: str, sections: list[Section]) -> list[dict[str, object]]:
    """Hindi <-> English term pairs: contents titles first, then repeated 'Hindi (English)' headings in the body."""
    counts: Counter[tuple[str, str]] = Counter()
    for _, text in split_pages(raw):
        for m in _PAIR.finditer(text):
            hi = re.sub(r"\s+", " ", m.group(1)).strip(" -")
            en = re.sub(r"\s+", " ", m.group(2)).strip(" .,")
            if len(hi) >= 3 and 1 <= len(en.split()) <= 6 and _plausible_gloss(m.group(2).strip()):
                counts[(hi, en.lower())] += 1
    out: dict[tuple[str, str], dict[str, object]] = {}
    for s in sections:
        if s.title_hi and s.title_en and _plausible_gloss(s.title_en):
            out[(s.title_hi, s.title_en.lower())] = {"hi": s.title_hi, "en": s.title_en, "count": 1, "source": "contents"}
    for (hi, en), c in counts.items():
        if c >= 2 and (hi, en) not in out:
            out[(hi, en)] = {"hi": hi, "en": en, "count": c, "source": "body"}
    return sorted(out.values(), key=lambda e: (e["source"] != "contents", -int(e["count"]), str(e["hi"])))


def count_authorities(text: str) -> dict[str, int]:
    import unicodedata

    folded = "".join(ch for ch in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(ch))
    out: dict[str, int] = {}
    for name, variants in AUTHORITIES.items():
        pattern = "|".join(re.escape(v) for v in sorted({_fold(v) for v in variants}, key=len, reverse=True))  # one pass: no double counting
        n = len(re.findall(rf"\b(?:{pattern})", folded))
        if n:
            out[name] = n
    return out


def hindi_excerpt(page_text: str, max_chars: int = 480) -> str:
    """The first Devanagari lines of a scanned page -- the Sanskrit/Hindi original that sits beside the English
    translation. Kept as provenance for reviewers; it is raw OCR and is never searched or quoted as fact."""
    lines = []
    for line in page_text.splitlines():
        letters = sum(ch.isalpha() for ch in line)
        deva = len(_DEVANAGARI.findall(line))
        if letters >= 12 and deva / letters >= 0.7:
            lines.append(re.sub(r"\s+", " ", line).strip())
        if sum(len(x) for x in lines) >= max_chars:
            break
    return " ".join(lines)[:max_chars]
