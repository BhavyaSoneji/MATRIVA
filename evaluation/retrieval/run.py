"""Retrieval evaluation harness (issue #16, Master Prompt Section 40).

Loads the labeled eval dataset, runs each query through the actual #6
hybrid_retrieve (keyword-only path -- no live embedding API needed, same
constraint the rest of this project has worked under), and reports
Recall@K, Precision@K, MRR, and nDCG@K, evaluated independently from
generation (#9). Writes a JSON report to evaluation/reports/.
"""

from __future__ import annotations

import json
import sys
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
from app.rag.retrieval import hybrid_retrieve
from app.schemas.knowledge import KnowledgeChunk

from retrieval.metrics import (
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

SEED_PATH = _REPO_ROOT / "knowledge" / "seed" / "seed.yaml"
EVAL_DATASET_PATH = _EVAL_DIR / "retrieval" / "eval_dataset.yaml"
REPORTS_DIR = _EVAL_DIR / "reports"
K = 5


def _documents_to_chunks(documents) -> list[KnowledgeChunk]:
    """Treat each seed document as a single chunk -- seed content is short
    enough that real semantic chunking (#3) isn't needed for this corpus."""
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


def run_evaluation(k: int = K) -> dict:
    raw_documents = yaml.safe_load(SEED_PATH.read_text())
    documents = load_and_validate_documents(raw_documents)
    chunks = _documents_to_chunks(documents)

    eval_cases = yaml.safe_load(EVAL_DATASET_PATH.read_text())

    per_query_results = []
    for case in eval_cases:
        result = hybrid_retrieve(case["query"], candidate_chunks=chunks, k=k)
        # Score against document_id, not source_id: multiple distinct
        # documents can legitimately share one source_id (e.g. all 5 IFCT
        # food entries come from the same "ifct-2017" source), so source_id
        # is not a unique relevance identifier and would double-count hits.
        retrieved_document_ids = [chunk.document_id for chunk, _score in result.chunks]
        relevant = {case["expected_document_id"]}

        per_query_results.append(
            {
                "query": case["query"],
                "expected_source": case["expected_source"],
                "expected_document_id": case["expected_document_id"],
                "expected_domain": case["expected_domain"],
                "retrieved_document_ids": retrieved_document_ids,
                "recall_at_k": recall_at_k(retrieved_document_ids, relevant, k),
                "precision_at_k": precision_at_k(retrieved_document_ids, relevant, k),
                "reciprocal_rank": reciprocal_rank(retrieved_document_ids, relevant),
                "ndcg_at_k": ndcg_at_k(retrieved_document_ids, relevant, k),
            }
        )

    n = len(per_query_results)
    aggregate = {
        "num_queries": n,
        "k": k,
        "mean_recall_at_k": sum(r["recall_at_k"] for r in per_query_results) / n,
        "mean_precision_at_k": sum(r["precision_at_k"] for r in per_query_results) / n,
        "mean_reciprocal_rank": sum(r["reciprocal_rank"] for r in per_query_results) / n,
        "mean_ndcg_at_k": sum(r["ndcg_at_k"] for r in per_query_results) / n,
    }

    by_domain: dict[str, list[dict]] = {}
    for r in per_query_results:
        by_domain.setdefault(r["expected_domain"], []).append(r)
    per_domain_summary = {
        domain: {
            "num_queries": len(results),
            "mean_recall_at_k": sum(r["recall_at_k"] for r in results) / len(results),
            "mean_reciprocal_rank": sum(r["reciprocal_rank"] for r in results) / len(results),
        }
        for domain, results in by_domain.items()
    }

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "aggregate": aggregate,
        "per_domain": per_domain_summary,
        "per_query": per_query_results,
    }


def main() -> None:
    report = run_evaluation()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "retrieval_eval_report.json"
    report_path.write_text(json.dumps(report, indent=2))

    print(f"[evaluation:retrieval] {report['aggregate']['num_queries']} queries evaluated")
    for key, value in report["aggregate"].items():
        print(f"  {key}: {value}")
    print(f"[evaluation:retrieval] report written to {report_path}")


if __name__ == "__main__":
    main()
