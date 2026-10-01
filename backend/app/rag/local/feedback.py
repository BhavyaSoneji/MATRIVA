"""Pseudo-relevance feedback (RM3-style query expansion), the classic way to recover vocabulary the user did not use.

After a first search, the passages that scored best are assumed relevant. Terms that are frequent in them, but rare
in the corpus as a whole, are added to the query with a small weight and the search is repeated. A question that says
"morning sickness" then also searches for "hyperemesis", "ginger", "nausea" -- words the best passages used.

Safeguards: only terms that are informative (idf), reasonably rare (document frequency cap) and not already in the
question are added; the expansion has a low weight so it can refine ranking but never override the user's own words.
"""

from __future__ import annotations

from collections import Counter

from app.rag.local.index import LocalIndex

FEEDBACK_DOCS = 4
FEEDBACK_TERMS = 8
MAX_DF_RATIO = 0.25
EXPANSION_WEIGHT = 0.25


def expansion_terms(
    index: LocalIndex,
    ranked: list[tuple[int, float]],
    query_terms: set[str],
    docs: int = FEEDBACK_DOCS,
    terms: int = FEEDBACK_TERMS,
) -> dict[str, float]:
    """{term: weight} for the best terms of the top `docs` passages. `ranked` is [(passage index, score)] best first."""
    top = ranked[:docs]
    if not top:
        return {}
    total = sum(max(s, 1e-9) for _, s in top)
    weights: Counter[str] = Counter()
    for i, score in top:
        p = index.passages[i]
        counts = Counter(p.tokens)
        length = max(len(p.tokens), 1)
        share = max(score, 1e-9) / total
        for term, tf in counts.items():
            if term in query_terms or len(term) < 4:
                continue
            df = index.df.get(term, 0)
            if df == 0 or df > MAX_DF_RATIO * index.size:
                continue
            weights[term] += share * (tf / length) * index.idf(term)
    if not weights:
        return {}
    best = weights.most_common(terms)
    peak = best[0][1]
    return {t: EXPANSION_WEIGHT * w / peak for t, w in best}
