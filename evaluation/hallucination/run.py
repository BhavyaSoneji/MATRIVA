"""Hallucination / grounding test suite (issue #19, Master Prompt Section 43).

Runs each out-of-corpus question through the real retrieval pipeline (#6)
against the validated seed corpus, then #19's grounding guard
(`generate_or_insufficient_evidence`) with a "poison" client that raises if
the LLM is ever called -- proving the fixed insufficient-evidence response
is returned WITHOUT letting the model fill the gap from general knowledge,
per Section 43.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import yaml

_EVAL_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _EVAL_DIR.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
for path in (_EVAL_DIR, _BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.evidence.ayurveda_provenance import load_and_validate_documents
from app.rag.context_packet import build_context_packet
from app.rag.grounding import (
    INSUFFICIENT_EVIDENCE_RESPONSE,
    generate_or_insufficient_evidence,
)
from app.rag.retrieval import hybrid_retrieve
from app.schemas.knowledge import KnowledgeChunk

SEED_PATH = _REPO_ROOT / "knowledge" / "seed" / "seed.yaml"
TEST_CASES_PATH = _EVAL_DIR / "hallucination" / "test_cases.yaml"
REPORTS_DIR = _EVAL_DIR / "reports"
K = 5


class _PoisonCompletions:
    def create(self, **kwargs):
        raise AssertionError("Groq was called for an out-of-corpus question -- Section 43 violated")


class _PoisonClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=_PoisonCompletions())


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


def run_evaluation() -> dict:
    chunks = _documents_to_chunks(
        load_and_validate_documents(yaml.safe_load(SEED_PATH.read_text()))
    )
    questions = [case["question"] for case in yaml.safe_load(TEST_CASES_PATH.read_text())]

    results = []
    for question in questions:
        retrieval = hybrid_retrieve(question, candidate_chunks=chunks, k=K)
        packet = build_context_packet(question, retrieval.chunks, safety_result={})
        try:
            response = generate_or_insufficient_evidence(
                packet, retrieval.chunks, client=_PoisonClient()
            )
            llm_was_called = False
        except AssertionError:
            response = None
            llm_was_called = True

        produced_insufficient_evidence = response == INSUFFICIENT_EVIDENCE_RESPONSE
        results.append(
            {
                "question": question,
                "response": response,
                "llm_was_called": llm_was_called,
                "produced_insufficient_evidence": produced_insufficient_evidence,
                "passed": produced_insufficient_evidence and not llm_was_called,
            }
        )

    n = len(results)
    passed = sum(1 for r in results if r["passed"])
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "num_questions": n,
        "num_passed": passed,
        "all_passed": passed == n,
        "cases": results,
    }


def main() -> None:
    report = run_evaluation()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "hallucination_eval_report.json"
    report_path.write_text(json.dumps(report, indent=2))

    print(f"[evaluation:hallucination] {report['num_passed']}/{report['num_questions']} passed")
    for case in report["cases"]:
        if not case["passed"]:
            print(f"  FAIL: {case['question']!r} -> llm_called={case['llm_was_called']}, response={case['response']!r}")
    print(f"[evaluation:hallucination] report written to {report_path}")


if __name__ == "__main__":
    main()
