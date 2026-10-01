"""Build backend/app/data/book_index.json: the knowledge representation of the Prasuti Tantra OCR.

    python backend/scripts/build_book_index.py

Contents of the index (all derived from the scan, deterministically):
  chapters   number, English + Hindi title, scanned-page range, verified sections, number of English chunks/words,
             top concepts (from the ontology), classical authorities cited, distinctive terms
  glossary   Hindi <-> English term pairs
  authorities  citation counts across the book
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
_ROOT = _BACKEND.parent
for p in (_BACKEND, _ROOT / "ingestion"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from pipelines.book_structure import build_glossary, build_outline, count_authorities  # noqa: E402
from pipelines.ocr_english import chunk_paragraphs, extract_paragraphs, split_pages  # noqa: E402

from app.rag.local.graph import KnowledgeGraph  # noqa: E402
from app.rag.local.text import STOPWORDS, tokens  # noqa: E402

BOOK = _ROOT / "knowledge" / "ayurveda" / "Prasuti-Tantra-OCR.txt"
OUT = _BACKEND / "app" / "data" / "book_index.json"


def build() -> dict:
    raw = BOOK.read_text(encoding="utf-8")
    pages = dict(split_pages(raw))
    chapters, stats = build_outline(raw)
    all_sections = [s for c in chapters for s in c.sections]
    glossary = build_glossary(raw, all_sections)

    per_chapter_text: dict[int, list[str]] = {}
    per_chapter_chunks: dict[int, int] = {}
    for ch in chapters:
        paras = []
        for page in range(ch.scan_start, ch.scan_end + 1):
            paras += extract_paragraphs(page, pages.get(page, ""))
        chunks = chunk_paragraphs(paras)
        per_chapter_text[ch.number] = [c.text for c in chunks]
        per_chapter_chunks[ch.number] = len(chunks)

    all_tokens = {n: [t for text in texts for t in tokens(text)] for n, texts in per_chapter_text.items()}
    graph = KnowledgeGraph.build([tokens(t) for texts in per_chapter_text.values() for t in texts])
    df: Counter[str] = Counter()
    for toks in all_tokens.values():
        df.update(set(toks))
    n_ch = len(chapters) or 1

    out_chapters = []
    totals: Counter[str] = Counter()
    for ch in chapters:
        text = "\n".join(per_chapter_text[ch.number])
        authorities = count_authorities(text)
        totals.update(authorities)
        concepts = Counter(c for t in per_chapter_text[ch.number] for c in graph.detect(tokens(t)))
        tf = Counter(t for t in all_tokens[ch.number] if t not in STOPWORDS and len(t) >= 5)
        scored = sorted(
            ((c * math.log(n_ch / df[t]), t) for t, c in tf.items() if c >= 4 and df[t] <= max(2, n_ch // 2)),
            reverse=True,
        )
        out_chapters.append({
            "number": ch.number,
            "title_en": ch.title_en,
            "title_hi": ch.title_hi,
            "scan_start": ch.scan_start,
            "scan_end": ch.scan_end,
            "english_chunks": per_chapter_chunks[ch.number],
            "english_words": len(text.split()),
            "sections": [{"title_en": s.title_en, "title_hi": s.title_hi, "printed_page": s.printed_page, "scan_page": s.scan_page}
                         for s in ch.sections],
            "concepts": [{"id": cid, "label": graph.concepts[cid].label, "count": n} for cid, n in concepts.most_common(8)],
            "authorities": dict(sorted(authorities.items(), key=lambda kv: -kv[1])),
            "key_terms": [t for _, t in scored[:12]],
        })

    return {
        "title": "Ayurvediya Prasutitantra evam Striroga, Part I: Prasutitantra",
        "author": "Prof. Premvati Tiwari",
        "publisher": "Chaukhambha Orientalia, Varanasi",
        "source": "knowledge/ayurveda/Prasuti-Tantra-OCR.txt (Tesseract OCR; not clinically reviewed)",
        "generated_at": datetime.now(UTC).date().isoformat(),
        "scan_note": "Each scanned image is a two-page spread, so printed page p is on scanned page 27 + (p-1)//2 (corrected locally by reading the text).",
        "chapters": out_chapters,
        "authorities": dict(totals.most_common()),
        "stats": {**stats, "glossary_pairs": len(glossary), "scanned_pages": len(pages),
                  "english_chunks": sum(per_chapter_chunks.values())},
        "glossary": glossary[:900],
    }


def main() -> int:
    index = build()
    OUT.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT} -- {len(index['chapters'])} chapters, {index['stats']['verified_sections']} verified sections, "
          f"{index['stats']['glossary_pairs']} glossary pairs, {len(index['authorities'])} authorities")
    for ch in index["chapters"]:
        top = ", ".join(a for a in list(ch["authorities"])[:3])
        print(f"  {ch['number']:>2} {ch['title_en'][:48]:48} p{ch['scan_start']}-{ch['scan_end']} "
              f"{len(ch['sections']):>2} sections {ch['english_chunks']:>3} chunks | {top}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
