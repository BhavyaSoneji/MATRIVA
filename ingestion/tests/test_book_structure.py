import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.book_structure import (
    build_outline,
    clean_hindi,
    count_authorities,
    detect_chapters,
    hindi_excerpt,
    locate,
    longest_non_decreasing,
    parse_number,
    to_scan,
)

BOOK = Path(__file__).resolve().parents[2] / "knowledge" / "ayurveda" / "Prasuti-Tantra-OCR.txt"


def test_printed_to_scanned_page_accounts_for_two_page_spreads() -> None:
    assert to_scan(1) == 27 and to_scan(2) == 27 and to_scan(3) == 28 and to_scan(197) == 125


def test_devanagari_numbers_parse() -> None:
    assert parse_number("१८८") == 188 and parse_number("205") == 205 and parse_number("एबी") is None


def test_longest_non_decreasing_drops_garbled_page_numbers() -> None:
    values = [10, 20, 14, 30, 40, 2, 50]
    assert [values[i] for i in longest_non_decreasing(values)] == [10, 20, 30, 40, 50]


def test_clean_hindi_drops_ocr_stragglers() -> None:
    assert clean_hindi("ता गर्भाधान-विधि") == "गर्भाधान-विधि"
    assert clean_hindi("४ गर्भिणी-चिह्न एवं परिचर्या") == "गर्भिणी-चिह्न एवं परिचर्या"


def test_locate_corrects_page_drift_by_reading_the_body() -> None:
    pages = {50: "nothing relevant here", 53: "the treatment of abortion is described under garbhasrava", 54: "other text"}
    # predicted scan page for printed 160 is 27+79=106 in the real book; here the title is on a different page entirely
    assert locate("Treatment of abortion", 55 * 2 - 53, {k: v.lower() for k, v in pages.items()}, window=4) == 53
    assert locate("Quantum chromodynamics", 100, {50: "milk"}) is None  # not found nearby -> rejected, not guessed


def test_authorities_are_counted_through_ocr_spellings() -> None:
    counts = count_authorities("Caraka says; Suéruta and SuSruta agree; Vagbhata I opines; Kaéyapa; caraka again")
    assert counts["Caraka"] == 2 and counts["Susruta"] == 2 and counts["Vagbhata"] == 1 and counts["Kasyapa"] == 1


def test_hindi_excerpt_keeps_only_devanagari_lines() -> None:
    text = "English line about milk and ghee here.\nयह एक हिन्दी पंक्ति है जो काफी लम्बी है\nanother english line"
    assert hindi_excerpt(text) == "यह एक हिन्दी पंक्ति है जो काफी लम्बी है"


def test_chapter_headings_are_found_in_page_order() -> None:
    pages = {
        30: "अध्याय १\nCHAPTER I\nशीर्षक\n(FIRST TITLE OF BOOK)\ntext",
        60: "अध्याय २ CHAPTER II\nदूसरा (SECOND TITLE\nSPANNING LINES)\ntext",
        10: "CHAPTER 9 (BEFORE THE BODY STARTS HERE)",
    }
    found = detect_chapters(pages)
    assert [(p, t) for p, t, _ in found] == [(30, "First Title Of Book"), (60, "Second Title Spanning Lines")]


@pytest.mark.skipif(not BOOK.exists(), reason="OCR file not in this checkout")
def test_real_book_outline() -> None:
    chapters, stats = build_outline(BOOK.read_text(encoding="utf-8"))
    assert [c.number for c in chapters] == list(range(1, 12))
    assert chapters[0].scan_start == 27 and chapters[10].title_en.startswith("Stanya Or Breast Milk")
    assert chapters[8].title_en == "Normal And Abnormal Puerperium" and chapters[8].scan_start == 297
    assert all(a.scan_end + 1 == b.scan_start for a, b in zip(chapters, chapters[1:]))  # contiguous, no overlap
    assert stats["verified_sections"] >= 80
    for ch in chapters:  # every section sits inside its chapter and in page order
        pages = [s.scan_page for s in ch.sections]
        assert pages == sorted(pages) and all(ch.scan_start <= p <= ch.scan_end for p in pages)
