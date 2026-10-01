"""Extract the readable English passages from the Prasuti Tantra OCR dump.

The book is bilingual: Sanskrit verses and Hindi commentary (Devanagari, badly mangled by OCR)
alternate with English translation paragraphs, which Tesseract reads far better. A retrieval
system searching English questions can only use the English parts, so this module:

1. splits the dump into scanned pages,
2. keeps only lines that are genuinely English prose,
3. cleans OCR debris and re-joins wrapped lines into paragraphs,
4. scores every paragraph with a transparent quality heuristic and drops the unreadable ones,
5. groups paragraphs into chunks (about 80-220 words) that remember their scanned-page span,
6. groups chunks into sections of a fixed number of pages, so a reviewer approves a few dozen
   small sections instead of one 4 MB document.

Nothing is invented or "fixed" semantically -- text is only cleaned, never rewritten -- and every
chunk keeps its page range so it can be checked against the scan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

PAGE_RE = re.compile(r"\n---\n## Scanned page (\d+)\n")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")

# Very common English words. A paragraph of real prose is full of these; OCR garbage is not.
_COMMON = frozenset(
    """the of and to in a is that it as for with was on are by this be or from at which an not have has
    had but they their its can may also these those when if then than such into more other one two
    after before during between should would could will been were he she his her we you your all any
    each both only same about over under through due use used using given give take taken food milk
    water body woman women mother child fetus foetus pregnancy pregnant month months delivery labour
    labor uterus blood time days day first second third fourth fifth sixth seventh eighth ninth
    treatment drug drugs disease diseases case cases symptoms pain diet diets regimen result results
    called known said say says according text texts important growth normal development
    dosha vata pitta kapha rasa ghee garbha sutika prasava""".split()
)
_JUNK_CHARS = re.compile(r"[|~^_=<>{}\\]|(?<=\s)[*#@$%]+(?=\s)")


@dataclass
class Paragraph:
    text: str
    page: int
    quality: float


@dataclass
class Chunk:
    text: str
    page_start: int
    page_end: int
    quality: float


@dataclass
class Section:
    title: str
    page_start: int
    page_end: int
    chunks: list[Chunk] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return sum(len(c.text.split()) for c in self.chunks)


def split_pages(raw: str) -> list[tuple[int, str]]:
    """[(scanned page number, page text)] from the OCR dump (header before page 1 is dropped)."""
    parts = PAGE_RE.split(raw)
    return [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]


def is_english_line(line: str) -> bool:
    """True for a line of English prose: mostly Latin letters, several real words, almost no Devanagari."""
    stripped = line.strip()
    if len(stripped) < 12:
        return False
    deva = len(_DEVANAGARI.findall(stripped))
    letters = sum(ch.isalpha() for ch in stripped)
    if letters == 0 or deva / letters > 0.08:
        return False
    return len(_WORD.findall(stripped)) >= 4


def clean_paragraph(text: str) -> str:
    text = _JUNK_CHARS.sub(" ", text)
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)  # re-join words hyphenated across lines
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def paragraph_quality(text: str) -> float:
    """0-1 readability score: share of tokens that are ordinary English, penalising symbol debris."""
    tokens = [t.lower().strip("'-") for t in _WORD.findall(text)]
    if len(tokens) < 8:
        return 0.0
    common = sum(t in _COMMON for t in tokens) / len(tokens)
    long_ok = sum(2 <= len(t) <= 14 for t in tokens) / len(tokens)
    symbols = sum(ch in "$#@%&*+=<>[]{}|\\^~`" for ch in text) / max(len(text), 1)
    digits = sum(ch.isdigit() for ch in text) / max(len(text), 1)
    if digits > 0.04:  # index pages, tables of page numbers, footnote lists
        return 0.0
    score = 0.7 * min(common / 0.35, 1.0) + 0.3 * long_ok - 4.0 * symbols
    return round(max(0.0, min(1.0, score)), 3)


def extract_paragraphs(page_no: int, page_text: str, *, min_quality: float = 0.65, min_words: int = 12) -> list[Paragraph]:
    out: list[Paragraph] = []
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        text = clean_paragraph(" ".join(buffer))
        buffer.clear()
        if len(text.split()) >= min_words:
            quality = paragraph_quality(text)
            if quality >= min_quality:
                out.append(Paragraph(text=text, page=page_no, quality=quality))

    for line in page_text.splitlines():
        if is_english_line(line):
            buffer.append(line.strip())
        elif not line.strip() or _DEVANAGARI.search(line):
            flush()  # a blank or Devanagari line ends the English paragraph
    flush()
    return out


def chunk_paragraphs(paragraphs: list[Paragraph], *, target_words: int = 140, max_words: int = 220) -> list[Chunk]:
    """Greedy packing of consecutive paragraphs into chunks, never splitting a paragraph."""
    chunks: list[Chunk] = []
    cur: list[Paragraph] = []
    words = 0

    def emit() -> None:
        nonlocal cur, words
        if cur:
            chunks.append(
                Chunk(
                    text="\n\n".join(p.text for p in cur),
                    page_start=cur[0].page,
                    page_end=cur[-1].page,
                    quality=round(sum(p.quality for p in cur) / len(cur), 3),
                )
            )
        cur, words = [], 0

    for para in paragraphs:
        n = len(para.text.split())
        if cur and words + n > max_words:
            emit()
        cur.append(para)
        words += n
        if words >= target_words:
            emit()
    emit()
    return chunks


def build_sections(raw: str, *, pages_per_section: int = 12, min_quality: float = 0.65) -> list[Section]:
    """The whole pipeline: raw OCR dump -> reviewable sections of clean English chunks."""
    pages = split_pages(raw)
    sections: list[Section] = []
    for start in range(0, len(pages), pages_per_section):
        group = pages[start : start + pages_per_section]
        paragraphs: list[Paragraph] = []
        for page_no, text in group:
            paragraphs.extend(extract_paragraphs(page_no, text, min_quality=min_quality))
        chunks = chunk_paragraphs(paragraphs)
        if not chunks:
            continue
        lo, hi = group[0][0], group[-1][0]
        sections.append(
            Section(
                title=f"Prasuti Tantra (Premvati Tiwari) - English passages, scanned pages {lo}-{hi}",
                page_start=lo,
                page_end=hi,
                chunks=chunks,
            )
        )
    return sections
