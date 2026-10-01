import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.ocr_english import (
    build_sections,
    chunk_paragraphs,
    clean_paragraph,
    extract_paragraphs,
    is_english_line,
    paragraph_quality,
    split_pages,
)

PROSE = (
    "Milk and ghee should be given to the pregnant woman in the later months because the text says "
    "that they nourish the mother and support the growth of the fetus during pregnancy."
)


def test_split_pages_numbers_and_drops_the_header() -> None:
    raw = "# header\n\n---\n## Scanned page 001\n\nfirst\n\n---\n## Scanned page 002\n\nsecond\n"
    assert [p for p, _ in split_pages(raw)] == [1, 2]


def test_english_line_detection() -> None:
    assert is_english_line("This is a clean line of English prose from the translation.")
    assert not is_english_line("अजमनि न यो हेतुर्विनाशे विकृतावषि। इमां स्त्रीनशुभान्‌ भावानाहुर्गर्भविघातकान्‌")
    assert not is_english_line("short")
    assert not is_english_line("मधुक, देवदारु milk of madhuka and some stray words appear here")


def test_clean_paragraph_rejoins_hyphenation_and_strips_debris() -> None:
    assert clean_paragraph("nourish- ment of the | fetus , is ~ important") == "nourishment of the fetus, is important"


def test_quality_separates_prose_from_index_pages_and_symbol_noise() -> None:
    assert paragraph_quality(PROSE) > 0.8
    assert paragraph_quality("agantuja 247] period 206) derived from aima 131 dauhrda 247 Dauhrdint 206 father 129") == 0.0
    assert paragraph_quality("$ # @ % & * + = < > [ ] { } | \\ ^ ~ ` xx yy zz qq ww ee rr tt") < 0.3


def test_extract_paragraphs_ends_at_devanagari_and_keeps_page() -> None:
    page = f"{PROSE}\nदेवनागरी पंक्ति\n{PROSE}\n"
    paras = extract_paragraphs(7, page)
    assert len(paras) == 2 and all(p.page == 7 for p in paras)


def test_chunks_respect_paragraph_boundaries_and_page_span() -> None:
    paras = []
    for page in (1, 2, 3):
        paras += extract_paragraphs(page, (PROSE + "\n\n") * 2)
    chunks = chunk_paragraphs(paras, target_words=40, max_words=80)
    assert len(chunks) >= 3
    assert all(len(c.text.split()) <= 80 + 40 for c in chunks)
    assert chunks[0].page_start == 1 and chunks[-1].page_end == 3


def test_build_sections_groups_pages_and_skips_empty_ones() -> None:
    raw = "# h\n" + "".join(f"\n---\n## Scanned page {n:03d}\n\n{PROSE}\n{PROSE}\n" for n in range(1, 25))
    sections = build_sections(raw, pages_per_section=12)
    assert [(s.page_start, s.page_end) for s in sections] == [(1, 12), (13, 24)]
    assert all(s.chunks and s.word_count > 0 for s in sections)
    assert build_sections("# h\n\n---\n## Scanned page 001\n\nदेवनागरी केवल\n") == []
