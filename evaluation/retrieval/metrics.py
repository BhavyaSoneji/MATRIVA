"""Retrieval evaluation metrics (issue #16, Master Prompt Section 40).

Pure functions, no dependency on the retrieval pipeline itself -- operate on
a ranked list of retrieved ids vs. a set of relevant ids, so they're testable
in isolation and reusable regardless of which retriever produced the ranking.
"""

from __future__ import annotations

import math


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    """Collapse repeated ids to their first occurrence. A retrieved list can
    legitimately contain the same document/source id more than once (e.g.
    multiple chunks from one document, or several documents sharing one
    source_id) -- without this, a single relevant item repeated across ranks
    would be double-counted as multiple hits, which can even push nDCG above
    1.0. Each distinct id should only ever count once."""
    seen: set[str] = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    ranked = _dedupe_preserve_order(retrieved)[:k]
    hits = len(set(ranked) & relevant)
    return hits / len(relevant)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if k == 0:
        return 0.0
    ranked = _dedupe_preserve_order(retrieved)[:k]
    hits = len(set(ranked) & relevant)
    return hits / k


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for rank, item in enumerate(_dedupe_preserve_order(retrieved), start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Binary relevance nDCG@k."""
    if not relevant:
        return 0.0

    ranked = _dedupe_preserve_order(retrieved)[:k]
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, item in enumerate(ranked, start=1)
        if item in relevant
    )
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    if idcg == 0:
        return 0.0
    return dcg / idcg
