"""Hybrid retrieval over the local index -- the middle of the RAG pipeline.

    query
      -> analyse   (stemmed tokens, corpus synonyms, concepts found, related concepts)
      -> filter    (pregnancy stage, region, domain)
      -> retrieve  (BM25 | character-n-gram TF-IDF | concept match -- three independent rankings)
      -> fuse      (reciprocal rank fusion)
      -> rerank    (query coverage, term proximity, concept coverage, evidence strength, text quality,
                    stage fit, diet fit)
      -> diversify (maximal marginal relevance + per-source / per-document caps)
      -> judge     (confidence, and whether the evidence is sufficient to answer at all)

Nothing here calls a model or the network.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.rag.local.corpus import Engine
from app.rag.local.index import K1
from app.rag.local.text import sentences, tokens

RRF_K = 60
CANDIDATES = 50
MMR_LAMBDA = 0.72
MAX_PER_SOURCE = 3
MAX_PER_DOCUMENT = 2

EVIDENCE_WEIGHT = {
    "supported": 1.0, "mixed_evidence": 0.8, "limited_evidence": 0.6, "preliminary": 0.55,
    "traditional": 0.55, "uncertain": 0.4, "not_established": 0.3,
}
_ANIMAL_CONCEPTS = frozenset({"meat", "fish", "liver"})

# Sufficiency gate -- when the evidence is too thin, answer nothing. Calibrated on evaluation/local_rag/questions.yaml
# (every out-of-scope question refused; see that suite). The three signals, all idf-weighted so a rare word like
# "epidural" counts far more than "first" or "risk":
#   sentence coverage -- the best single sentence in the top passages must contain a real share of the question,
#   union coverage    -- the top passages together must cover at least half of it,
#   top coverage      -- the best passage must contain a third of the question's terms.
MIN_COVERAGE = 0.34
MIN_SENTENCE_COVERAGE = 0.30
MIN_UNION_COVERAGE = 0.50
TOP_FOR_EVIDENCE = 5


@dataclass
class Hit:
    idx: int
    id: str
    meta: dict[str, Any]
    text: str
    score: float = 0.0
    bm25: float = 0.0
    ngram: float = 0.0
    concept: float = 0.0
    coverage: float = 0.0
    proximity: float = 0.0
    matched_terms: list[str] = field(default_factory=list)
    matched_concepts: list[str] = field(default_factory=list)


@dataclass
class UserProfile:
    stage: str | None = None
    region: str | None = None
    diet: str | None = None
    allergies: list[str] = field(default_factory=list)


@dataclass
class Retrieval:
    hits: list[Hit]
    query_tokens: list[str]
    concepts: list[str]
    expanded: dict[str, float]
    confidence: float
    sufficient: bool
    reason: str
    pool: int = 0  # how many passages passed the filters
    sentence_coverage: float = 0.0
    union_coverage: float = 0.0


def _rank(scores: dict[int, float]) -> dict[int, int]:
    ordered = sorted(scores, key=lambda i: -scores[i])[:CANDIDATES]
    return {i: r for r, i in enumerate(ordered, start=1)}


def _proximity(passage_tokens: list[str], matched: set[str]) -> float:
    """How tightly the matched query words cluster: matched_count / span of the smallest window holding all of them."""
    if len(matched) < 2:
        return 0.0
    positions = [(pos, t) for pos, t in enumerate(passage_tokens) if t in matched]
    need, have, best, left = len(matched), {}, None, 0
    for right, (pos_r, tok_r) in enumerate(positions):
        have[tok_r] = have.get(tok_r, 0) + 1
        while len(have) == need:
            span = pos_r - positions[left][0] + 1
            best = span if best is None else min(best, span)
            tok_l = positions[left][1]
            have[tok_l] -= 1
            if not have[tok_l]:
                del have[tok_l]
            left += 1
    return min(1.0, need / best) if best else 0.0


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def search(engine: Engine, query: str, *, profile: UserProfile | None = None, k: int = 6,
           domains: set[str] | None = None) -> Retrieval:
    profile = profile or UserProfile()
    index, graph = engine.index, engine.graph
    q_tokens = list(dict.fromkeys(tokens(query)))
    if not q_tokens or index.size == 0:
        return Retrieval([], q_tokens, [], {}, 0.0, False, "empty query or empty knowledge base")

    concepts = graph.detect(q_tokens)
    expanded = graph.expand(concepts)

    # ---- filters (a stage-specific passage for another stage is out; unspecified stage applies to all)
    allowed = {
        i
        for i, p in enumerate(index.passages)
        if (profile.stage is None or p.meta.get("stage") in (None, "all", profile.stage))
        and (profile.region is None or p.meta.get("region") in (None, profile.region))
        and (domains is None or p.meta.get("domain") in domains)
    }
    if not allowed:  # never let a filter silently return nothing when the unfiltered corpus has candidates
        allowed = set(range(index.size))

    # ---- three independent retrievals
    weights: dict[str, float] = {t: 1.0 for t in q_tokens}
    for cid, w in expanded.items():  # related concepts add a quieter signal
        for term in (graph.concepts[cid].phrases[0] if graph.concepts[cid].phrases else ()):
            weights.setdefault(term, 0.0)
            weights[term] = max(weights[term], 0.35 * w)
    bm25 = index.bm25(weights, allowed)
    ngram = index.ngram_cosine(query, allowed)
    q_concepts = set(concepts)
    concept_score: dict[int, float] = {}
    total_w = len(q_concepts) + 0.5 * sum(1 for _ in expanded) or 1.0
    for i in allowed:
        present = graph.passage_concepts[i]
        s = len(q_concepts & present) + 0.5 * sum(1 for cid in expanded if cid in present)
        if s:
            concept_score[i] = s / total_w

    ranks = [_rank(bm25), _rank(ngram), _rank(concept_score)]
    fused: dict[int, float] = {}
    for r in ranks:
        for i, rank in r.items():
            fused[i] = fused.get(i, 0.0) + 1.0 / (RRF_K + rank)
    if not fused:
        return Retrieval([], q_tokens, concepts, expanded, 0.0, False, "nothing matched the question", len(allowed))
    top_fused = max(fused.values())
    max_bm25 = sum(w * index.idf(t) * (K1 + 1) for t, w in weights.items()) or 1.0

    # ---- rerank on interpretable features
    qset = set(q_tokens)
    hits: list[Hit] = []
    for i, f in fused.items():
        p = index.passages[i]
        matched = qset & p.token_set
        coverage = len(matched) / len(qset)
        concept_cov = len(q_concepts & graph.passage_concepts[i]) / len(q_concepts) if q_concepts else 0.0
        prox = _proximity(p.tokens, matched)
        evidence = EVIDENCE_WEIGHT.get(str(p.meta.get("evidence_level", "")).lower(), 0.5)
        quality = float(p.meta.get("readability", 1.0))
        stage_fit = 1.0 if profile.stage and p.meta.get("stage") == profile.stage else 0.0
        score = (
            0.45 * f / top_fused
            + 0.20 * coverage
            + 0.10 * prox
            + 0.10 * concept_cov
            + 0.05 * evidence
            + 0.05 * quality
            + 0.05 * stage_fit
        )
        if profile.diet in {"vegetarian", "vegan"} and (graph.passage_concepts[i] & _ANIMAL_CONCEPTS) and not (
            q_concepts & _ANIMAL_CONCEPTS
        ):
            score *= 0.85  # the question is not about meat/fish, so prefer passages that fit this diet
        hits.append(
            Hit(
                idx=i, id=p.id, meta=p.meta, text=p.text, score=score,
                bm25=bm25.get(i, 0.0) / max_bm25, ngram=ngram.get(i, 0.0), concept=concept_cov,
                coverage=coverage, proximity=prox,
                matched_terms=sorted(matched), matched_concepts=sorted(q_concepts & graph.passage_concepts[i]),
            )
        )
    hits.sort(key=lambda h: -h.score)
    pool = hits[: CANDIDATES]

    # ---- diversify: MMR with per-source / per-document caps
    chosen: list[Hit] = []
    per_source: dict[str, int] = {}
    per_doc: dict[str, int] = {}
    remaining = list(pool)
    while remaining and len(chosen) < k:
        best, best_val = None, -math.inf
        for h in remaining:
            if per_source.get(h.meta["source_id"], 0) >= MAX_PER_SOURCE or per_doc.get(h.meta["document_id"], 0) >= MAX_PER_DOCUMENT:
                continue
            sim = max((_jaccard(index.passages[h.idx].token_set, index.passages[c.idx].token_set) for c in chosen), default=0.0)
            val = MMR_LAMBDA * h.score - (1 - MMR_LAMBDA) * sim
            if val > best_val:
                best, best_val = h, val
        if best is None:
            break
        chosen.append(best)
        remaining.remove(best)
        per_source[best.meta["source_id"]] = per_source.get(best.meta["source_id"], 0) + 1
        per_doc[best.meta["document_id"]] = per_doc.get(best.meta["document_id"], 0) + 1

    # ---- judge
    if not chosen:
        return Retrieval([], q_tokens, concepts, expanded, 0.0, False, "no passage survived filtering", len(allowed))
    top = chosen[0]
    max_idf = math.log(1 + (index.size + 0.5) / 0.5)

    def weight(term: str) -> float:  # a word that appears nowhere in the corpus is maximally informative -- and unmatched
        return index.idf(term) if index.df.get(term) else max_idf

    total = sum(weight(t) for t in q_tokens) or 1.0
    best_sentence, union = 0.0, set()
    for hit in chosen[:TOP_FOR_EVIDENCE]:
        union |= qset & index.passages[hit.idx].token_set
        for sent in sentences(hit.text) or [hit.text]:
            best_sentence = max(best_sentence, sum(weight(t) for t in qset & set(tokens(sent))) / total)
    union_cov = sum(weight(t) for t in union) / total
    confidence = round(min(1.0, 0.40 * min(best_sentence / 0.8, 1.0) + 0.35 * union_cov + 0.25 * top.coverage), 3)
    sufficient = (
        top.coverage >= MIN_COVERAGE and best_sentence >= MIN_SENTENCE_COVERAGE and union_cov >= MIN_UNION_COVERAGE
    )
    reason = (
        "enough evidence"
        if sufficient
        else (
            f"the closest passages match only part of the question (best sentence {best_sentence:.0%}, "
            f"passages together {union_cov:.0%}, best passage {top.coverage:.0%}); not enough to answer reliably"
        )
    )
    return Retrieval(chosen, q_tokens, concepts, expanded, confidence, sufficient, reason, len(allowed), round(best_sentence, 3), round(union_cov, 3))
