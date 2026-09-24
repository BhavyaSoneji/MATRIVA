"""Generation evaluation harness (issue #17, Master Prompt Section 41).

Two modes:
- LIVE: if LLM_API_KEY/GROQ_API_KEY is set, retrieves+generates real answers
  for the retrieval eval dataset's queries via the actual pipeline (#6-#9)
  and scores them.
- SELF-TEST: no API key available (the case in this environment) --
  evaluates a small set of hand-authored example responses (a grounded one,
  an ungrounded one, an incomplete one) against the same metrics, so the
  scoring logic itself is exercised and demonstrated even without a live
  model. Clearly labeled in the report which mode produced it.

Clarity and final quality assessment are NOT scored here -- Section 41:
"use human review for final quality assessment." See
human_review_checklist.md.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import yaml

_EVAL_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _EVAL_DIR.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
for path in (_EVAL_DIR, _BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.evidence.ayurveda_provenance import load_and_validate_documents
from app.llm.groq_client import GenerationError, generate_from_packet
from app.rag.context_packet import build_context_packet
from app.rag.retrieval import hybrid_retrieve
from app.safety.classifier import classify
from app.schemas.knowledge import KnowledgeChunk

from generation.metrics import (
    answer_relevance,
    citation_correctness,
    completeness_check,
    groundedness_check,
)

SEED_PATH = _REPO_ROOT / "knowledge" / "seed" / "seed.yaml"
RETRIEVAL_EVAL_PATH = _EVAL_DIR / "retrieval" / "eval_dataset.yaml"
REPORTS_DIR = _EVAL_DIR / "reports"
K = 5

_SELF_TEST_CASES = [
    {
        "label": "grounded_with_citation",
        "query": "Is spinach good for iron during pregnancy?",
        "response": "Spinach is a commonly recommended source of iron during pregnancy [seed-ifct-palak-001].",
    },
    {
        "label": "ungrounded_unsupported_claim",
        "query": "Is spinach good for iron during pregnancy?",
        "response": "You have anemia and spinach will definitely cure it immediately.",
    },
    {
        "label": "fabricated_citation",
        "query": "Is spinach good for iron during pregnancy?",
        "response": "Spinach helps with iron levels [nonexistent-source-42].",
    },
    {
        "label": "too_short",
        "query": "Is spinach good for iron during pregnancy?",
        "response": "Yes.",
    },
]


def _documents_to_chunks(documents) -> list[KnowledgeChunk]:
    return [
        KnowledgeChunk(
            chunk_id=f"{doc.document_id}-chunk-0000",
            document_id=doc.document_id,
            source_id=doc.source_id,
            domain=doc.domain,
            topic=doc.topic,
            pregnancy_stage=doc.pregnancy_stage,
            evidence_level=doc.evidence_level,
            region=doc.region,
            language=doc.language,
            content=f"{doc.title} {doc.content}",
            chunk_index=0,
        )
        for doc in documents
    ]


def _score_case(query: str, response: str, context_packet) -> dict:
    citation = citation_correctness(response, context_packet)
    groundedness = groundedness_check(response, context_packet)
    completeness = completeness_check(response, context_packet)
    return {
        "query": query,
        "response": response,
        "citation_correctness": asdict(citation),
        "groundedness": asdict(groundedness),
        "answer_relevance": answer_relevance(query, response),
        "completeness": asdict(completeness),
    }


def run_self_test() -> dict:
    chunks = _documents_to_chunks(
        load_and_validate_documents(yaml.safe_load(SEED_PATH.read_text()))
    )
    results = []
    for case in _SELF_TEST_CASES:
        retrieval = hybrid_retrieve(case["query"], candidate_chunks=chunks, k=K)
        packet = build_context_packet(case["query"], retrieval.chunks, safety_result={})
        scored = _score_case(case["query"], case["response"], packet)
        scored["label"] = case["label"]
        results.append(scored)
    return {"mode": "SELF_TEST", "cases": results}


def run_live() -> dict:
    chunks = _documents_to_chunks(
        load_and_validate_documents(yaml.safe_load(SEED_PATH.read_text()))
    )
    eval_cases = yaml.safe_load(RETRIEVAL_EVAL_PATH.read_text())

    results = []
    for case in eval_cases:
        query = case["query"]
        retrieval = hybrid_retrieve(query, candidate_chunks=chunks, k=K)
        safety_result = asdict(classify(query))
        packet = build_context_packet(query, retrieval.chunks, safety_result=safety_result)
        try:
            response = generate_from_packet(packet)
        except GenerationError as exc:
            results.append({"query": query, "error": str(exc)})
            continue
        scored = _score_case(query, response, packet)
        results.append(scored)
    return {"mode": "LIVE", "cases": results}


def main() -> None:
    has_key = bool(os.environ.get("LLM_API_KEY") or os.environ.get("GROQ_API_KEY"))
    report = run_live() if has_key else run_self_test()
    report["generated_at"] = datetime.now(UTC).isoformat()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "generation_eval_report.json"
    report_path.write_text(json.dumps(report, indent=2))

    print(f"[evaluation:generation] mode={report['mode']}, {len(report['cases'])} cases scored")
    print(f"[evaluation:generation] report written to {report_path}")
    print("[evaluation:generation] clarity/final quality assessment: see human_review_checklist.md")


if __name__ == "__main__":
    main()
