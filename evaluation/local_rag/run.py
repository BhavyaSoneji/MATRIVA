"""Evaluation of the offline RAG engine on the project's real corpus.

Builds the index straight from the repository's data files -- seed.yaml, guidelines.yaml, foods.yaml and the
Prasuti Tantra English sections -- treating them as approved (the point is to measure retrieval quality, not
the review workflow), then asks every question in questions.yaml and reports:

  * hit@1 / hit@3 / hit@5 and MRR for in-scope questions (right document, or right words for the book),
  * refusal precision: out-of-scope questions must be judged INSUFFICIENT,
  * how often the engine answered in-scope questions at all (coverage).

Usage:  python evaluation/local_rag/run.py [--no-book]
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[2]
for p in (_REPO / "backend", _REPO / "ingestion"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from pipelines.book_structure import build_outline, section_for  # noqa: E402
from pipelines.ocr_english import chunk_paragraphs, extract_paragraphs, split_pages  # noqa: E402

from app.rag.local.composer import compose  # noqa: E402
from app.rag.local.corpus import Engine  # noqa: E402
from app.rag.local.index import Passage  # noqa: E402
from app.rag.local.retriever import DEFAULT as DEFAULT_CONFIG  # noqa: E402
from app.rag.local.retriever import Config, search  # noqa: E402
from app.rag.local.text import tokens  # noqa: E402

QUESTIONS = Path(__file__).with_name("questions.yaml")
REPORT = _REPO / "evaluation" / "reports" / "local_rag_eval_report.json"
BOOK = _REPO / "knowledge" / "ayurveda" / "Prasuti-Tantra-OCR.txt"


def build_passages(include_book: bool = True) -> list[Passage]:
    passages: list[Passage] = []
    entries: list[dict] = []
    for name in ("seed.yaml", "guidelines.yaml", "foods.yaml"):
        entries += yaml.safe_load((_REPO / "knowledge" / "seed" / name).read_text(encoding="utf-8"))
    for e in entries:
        stage = e.get("pregnancy_stage")
        passages.append(
            Passage(
                id=e["document_id"],
                text=e["content"].strip(),
                tokens=tokens(f"{e['content']} {e['title']} {e.get('topic', '')}"),
                meta={
                    "title": e["title"], "document_id": e["document_id"], "source_id": e.get("source_id", e["document_id"]),
                    "topic": e.get("topic"), "domain": e["domain"].lower(), "stage": None if stage in (None, "all") else stage,
                    "region": e.get("region"), "evidence_level": e["evidence_level"].lower(),
                    "source_type": "traditional" if e["domain"] == "AYURVEDA" else "government", "locator": None,
                },
            )
        )
    if include_book and BOOK.exists():
        raw = BOOK.read_text(encoding="utf-8")
        pages = dict(split_pages(raw))
        chapters, _ = build_outline(raw)
        for ch in chapters:
            paras = []
            for page in range(ch.scan_start, ch.scan_end + 1):
                paras += extract_paragraphs(page, pages.get(page, ""))
            for i, chunk in enumerate(chunk_paragraphs(paras)):
                sec = section_for(ch, chunk.page_start)
                title = f"Prasuti Tantra - Chapter {ch.number}: {ch.title_en}"
                passages.append(
                    Passage(
                        id=f"book-ch{ch.number}-{i}",
                        text=chunk.text,
                        tokens=tokens(f"{chunk.text} {title} {sec.title_en if sec else ''} {ch.title_en}"),
                        meta={
                            "title": title, "document_id": f"book-ch{ch.number}", "source_id": "prasuti-tantra",
                            "domain": "ayurveda", "stage": None, "region": "IN", "evidence_level": "traditional",
                            "source_type": "traditional", "readability": chunk.quality, "chapter": ch.number,
                            "section": sec.title_en if sec else None,
                            "locator": f"Ch. {ch.number} \u203a {sec.title_en if sec else ''} \u00b7 scanned p. {chunk.page_start}",
                        },
                    )
                )
    return passages


def evaluate(include_book: bool = True, k: int = 5, questions: Path = QUESTIONS, config: Config = DEFAULT_CONFIG,
             engine: Engine | None = None) -> dict:
    engine = engine or Engine(build_passages(include_book))
    spec = yaml.safe_load(questions.read_text(encoding="utf-8"))
    cases, ranks = [], []
    answered = 0
    for item in spec["in_scope"]:
        if item.get("expect_text") and not item.get("expect_docs") and not include_book:
            continue
        r = search(engine, item["q"], k=k, config=config)
        found_rank = None
        for rank, hit in enumerate(r.hits[:k], start=1):
            doc_ok = hit.id in item.get("expect_docs", [])
            text_ok = any(w.lower() in hit.text.lower() for w in item.get("expect_text", []))
            if doc_ok or (not item.get("expect_docs") and text_ok):
                found_rank = rank
                break
        answered += r.sufficient
        ranks.append(found_rank)
        cases.append({"question": item["q"], "found_rank": found_rank, "sufficient": r.sufficient,
                      "confidence": r.confidence, "top": [h.id for h in r.hits[:3]]})
    refusals = []
    for q in spec["out_of_scope"]:
        r = search(engine, q, k=k, config=config)
        refusals.append({"question": q, "refused": not r.sufficient, "confidence": r.confidence,
                         "reason": r.reason, "top": [h.id for h in r.hits[:2]]})

    n = len(ranks) or 1
    metrics = {
        "in_scope": len(ranks),
        "hit_at_1": round(sum(1 for r in ranks if r == 1) / n, 3),
        "hit_at_3": round(sum(1 for r in ranks if r and r <= 3) / n, 3),
        "hit_at_5": round(sum(1 for r in ranks if r and r <= 5) / n, 3),
        "mrr": round(sum(1 / r for r in ranks if r) / n, 3),
        "answered_in_scope": round(answered / n, 3),
        "out_of_scope": len(refusals),
        "refusal_precision": round(sum(c["refused"] for c in refusals) / (len(refusals) or 1), 3),
        "passages": len(engine.index.passages),
        "graph": engine.graph.stats(),
    }
    return {"generated_at": datetime.now(UTC).isoformat(), "engine": "local", "book_included": include_book,
            "metrics": metrics, "in_scope_cases": cases, "out_of_scope_cases": refusals}


HELDOUT = Path(__file__).with_name("heldout.yaml")


def main() -> int:
    if any(a in sys.argv for a in ("--heldout", "--heldout2", "--heldout3")):
        which = HELDOUT.with_name("heldout3.yaml") if "--heldout3" in sys.argv else HELDOUT.with_name("heldout2.yaml") if "--heldout2" in sys.argv else HELDOUT
        report = evaluate(questions=which)
        print(json.dumps(report["metrics"], indent=2))
        for c in report["in_scope_cases"]:
            print(f"  {'ok  ' if c['found_rank'] else 'MISS'} rank={c['found_rank']} sufficient={c['sufficient']} {c['question']} -> {c['top']}")
        for c in report["out_of_scope_cases"]:
            print(f"  {'refused ' if c['refused'] else 'ANSWERED'} {c['question']} -> {c['top']}")
        (REPORT.parent / f"local_rag_{which.stem}_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 0
    report = evaluate(include_book="--no-book" not in sys.argv)
    m = report["metrics"]
    print(json.dumps(m, indent=2))
    for c in report["in_scope_cases"]:
        if not c["found_rank"] or not c["sufficient"]:
            print(f"  MISS rank={c['found_rank']} sufficient={c['sufficient']} conf={c['confidence']}: {c['question']} -> {c['top']}")
    for c in report["out_of_scope_cases"]:
        if not c["refused"]:
            print(f"  ANSWERED OOS (conf {c['confidence']}): {c['question']} -> {c['top']}")
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"report written to {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
