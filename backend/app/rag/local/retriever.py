"""Advanced hybrid retrieval over the local index -- the middle of the RAG pipeline.

    question
      -> understand   intent (definition / quantity / safety / how-to / list / comparison), authorities named,
                      compound questions split when their halves are never discussed together
      -> analyse      stemmed tokens, corpus synonyms, concepts found, related concepts (knowledge graph)
      -> filter       region and domain (pregnancy stage is a preference, applied in the rerank)
      -> retrieve     seven independent signals, each its own ranking:
                        BM25 (words) | character n-gram TF-IDF (OCR / spelling tolerant) | concept match |
                        latent semantic analysis (same meaning, different words) |
                        structure (section / chapter titles) | graph activation (personalised PageRank over the
                        concept graph: multi-hop) | pseudo-relevance feedback (vocabulary the best passages use)
      -> fuse         weighted reciprocal rank fusion
      -> rerank       coverage, term proximity, concept coverage, title match, semantic similarity, evidence strength,
                      text quality, stage fit, diet fit, authority named in the question
      -> diversify    maximal marginal relevance + per-source / per-document caps
      -> judge        idf-weighted sufficiency gate: answer, or refuse

Every signal can be switched off through `Config`, which is how the ablation study in evaluation/local_rag measures what
each one contributes. Nothing here calls a model or the network.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from app.rag.local import feedback
from app.rag.local.corpus import Engine
from app.rag.local.index import K1
from app.rag.local.text import sentences, tokens
from app.rag.local.understanding import QueryPlan, analyze

RRF_K = 60
CANDIDATES = 50
MMR_LAMBDA = 0.72
MAX_PER_SOURCE = 3
MAX_PER_DOCUMENT = 2
MAX_NUTRIENT_TABLES = 2  # per-food nutrient tables: useful, but they must not crowd out guidance

EVIDENCE_WEIGHT = {
    "supported": 1.0, "mixed_evidence": 0.8, "limited_evidence": 0.6, "preliminary": 0.55,
    "traditional": 0.55, "uncertain": 0.4, "not_established": 0.3,
}
_ANIMAL_CONCEPTS = frozenset({"meat", "fish", "liver"})
_FOOD_TYPES = frozenset({"food"})
# Asking "what does Ayurveda say..." is a request for traditional sources; prefer them (softly).
TRADITIONAL_CUES = frozenset({"ayurveda", "charaka", "susruta", "sushruta", "vagbhata", "kashyapa", "samhita", "classical"})

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


@dataclass(frozen=True)
class Config:
    """Which retrieval signals are on. The defaults are the production pipeline; the ablation study flips them."""

    bm25: bool = True
    ngram: bool = True
    concept: bool = True
    semantic: bool = True  # latent semantic analysis
    structure: bool = True  # section / chapter titles
    graph: bool = True  # personalised PageRank over the concept graph
    feedback: bool = True  # pseudo-relevance feedback
    authority: bool = True
    decompose: bool = True


DEFAULT = Config()

# weight of each signal's ranking in the fusion
SIGNAL_WEIGHT = {"bm25": 1.0, "ngram": 0.7, "concept": 0.7, "semantic": 0.4, "structure": 0.8, "graph": 0.3, "feedback": 0.5}


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
    semantic: float = 0.0
    structure: float = 0.0
    graph: float = 0.0
    coverage: float = 0.0
    proximity: float = 0.0
    covered: frozenset[str] = frozenset()  # question terms the passage covers, literally or through a concept
    matched_terms: list[str] = field(default_factory=list)
    matched_concepts: list[str] = field(default_factory=list)
    authorities: list[str] = field(default_factory=list)  # authorities named in the question that this passage cites


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
    quantity_intent: bool = False  # "how much / how many / dose": prefer sentences that state a number
    intent: str = "general"
    authorities: list[str] = field(default_factory=list)  # authorities named in the question
    feedback_terms: list[str] = field(default_factory=list)  # words the best passages added to the search
    activated: list[str] = field(default_factory=list)  # concepts reached by graph activation (beyond those asked)
    sub_queries: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)  # which retrieval signals contributed candidates


_QUANTITY_RE = re.compile(r"\bhow (?:much|many|often|long)\b|\bdose\b|\bdosage\b|\bamount\b|\bquantit|\bportions?\b|\bper day\b|\bhow big\b", re.IGNORECASE)


def wants_quantity(query: str) -> bool:
    return bool(_QUANTITY_RE.search(query))


def _rank(scores: dict[int, float]) -> dict[int, int]:
    ordered = sorted(scores, key=lambda i: -scores[i])[:CANDIDATES]
    return {i: r for r, i in enumerate(ordered, start=1)}


def _proximity(passage_tokens: list[str], matched: set[str]) -> float:
    """How tightly the matched query words cluster: matched_count / span of the smallest window holding all of them."""
    if len(matched) < 2:
        return 0.0
    positions = [(pos, t) for pos, t in enumerate(passage_tokens) if t in matched]
    have: dict[str, int] = {}
    need, best, left = len(matched), None, 0
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
           domains: set[str] | None = None, config: Config = DEFAULT) -> Retrieval:
    """Retrieve for `query`. Compound questions whose halves are never discussed together are retrieved part by part
    and merged round-robin, so neither half drowns the other."""
    plan = analyze(query, engine.graph, decompose=config.decompose)
    if len(plan.sub_queries) >= 2:
        subs = [_search_one(engine, q, plan, profile, max(2, math.ceil(k / len(plan.sub_queries))), domains, config)
                for q in plan.sub_queries]
        merged: list[Hit] = []
        seen: set[str] = set()
        for rank in range(max(len(r.hits) for r in subs)):
            for r in subs:
                if rank < len(r.hits) and r.hits[rank].id not in seen:
                    seen.add(r.hits[rank].id)
                    merged.append(r.hits[rank])
        if merged and any(r.sufficient for r in subs):
            best = max(subs, key=lambda r: r.confidence)
            best_tokens = list(dict.fromkeys(t for r in subs for t in r.query_tokens))
            return Retrieval(
                merged[:k], best_tokens, list(dict.fromkeys(c for r in subs for c in r.concepts)), best.expanded,
                round(sum(r.confidence for r in subs) / len(subs), 3), True, "enough evidence (each part of the question answered separately)",
                best.pool, best.sentence_coverage, best.union_coverage, wants_quantity(query), plan.intent,
                plan.authorities, [t for r in subs for t in r.feedback_terms], [c for r in subs for c in r.activated],
                plan.sub_queries, best.signals,
            )
    return _search_one(engine, query, plan, profile, k, domains, config)


def _search_one(engine: Engine, query: str, plan: QueryPlan, profile: UserProfile | None, k: int,
                domains: set[str] | None, config: Config) -> Retrieval:
    profile = profile or UserProfile()
    index, graph = engine.index, engine.graph
    q_tokens = list(dict.fromkeys(tokens(query)))
    if not q_tokens or index.size == 0:
        return Retrieval([], q_tokens, [], {}, 0.0, False, "empty query or empty knowledge base", intent=plan.intent)

    spans = graph.detect_spans(q_tokens)
    concepts = list(spans)
    expanded = graph.expand(concepts)
    q_concepts = set(concepts)
    qset = set(q_tokens)
    # "...in Ayurveda" names the kind of source wanted; it is not a word the passage has to contain
    content = (qset - TRADITIONAL_CUES) or qset

    # ---- filters. Region and domain are hard filters; pregnancy stage is only a preference (see the rerank):
    # morning sickness is "first trimester" content, but a woman in week 22 may still ask about it.
    allowed = {
        i
        for i, p in enumerate(index.passages)
        if (profile.region is None or p.meta.get("region") in (None, profile.region))
        and (domains is None or p.meta.get("domain") in domains)
    }
    if not allowed:  # never let a filter silently return nothing when the unfiltered corpus has candidates
        allowed = set(range(index.size))

    # ---- signal 1-3: BM25, character n-grams, concept match
    weights: dict[str, float] = {t: 1.0 for t in q_tokens}
    for cid, w in expanded.items():  # related concepts add a quieter signal
        for term in (graph.concepts[cid].phrases[0] if graph.concepts[cid].phrases else ()):
            weights.setdefault(term, 0.0)
            weights[term] = max(weights[term], 0.35 * w)
    bm25 = index.bm25(weights, allowed) if config.bm25 else {}
    ngram = index.ngram_cosine(query, allowed) if config.ngram else {}
    concept_score: dict[int, float] = {}
    if config.concept:
        total_w = len(q_concepts) + 0.5 * sum(1 for _ in expanded) or 1.0
        for i in allowed:
            present = graph.passage_concepts[i]
            s = len(q_concepts & present) + 0.5 * sum(1 for cid in expanded if cid in present)
            if s:
                concept_score[i] = s / total_w

    # ---- signal 4: latent semantic analysis
    semantic = index.semantic.scores(q_tokens, allowed) if config.semantic else {}

    # ---- signal 5: structure (section / chapter / document titles)
    structure = index.structure_scores(qset, allowed) if config.structure else {}

    # ---- signal 6: graph activation (multi-hop over the concept graph)
    graph_score: dict[int, float] = {}
    activated: list[str] = []
    if config.graph and q_concepts:
        activation = graph.activation({c: 1.0 for c in q_concepts})
        activated = [c for c, a in sorted(activation.items(), key=lambda kv: -kv[1]) if c not in q_concepts and a > 0.02][:6]
        for i in allowed:
            present = graph.passage_concepts[i]
            if present:
                a = sum(activation.get(c, 0.0) for c in present)
                if a > 0:
                    graph_score[i] = a / math.sqrt(len(present))

    # ---- first fusion, then signal 7: pseudo-relevance feedback from the passages that fused best
    signals = {"bm25": bm25, "ngram": ngram, "concept": concept_score, "semantic": semantic,
               "structure": structure, "graph": graph_score}

    def fuse(sig: dict[str, dict[int, float]]) -> dict[int, float]:
        out: dict[int, float] = {}
        for name, scores in sig.items():
            for i, rank in _rank(scores).items():
                out[i] = out.get(i, 0.0) + SIGNAL_WEIGHT[name] / (RRF_K + rank)
        return out

    fused = fuse(signals)
    feedback_terms: list[str] = []
    if config.feedback and fused and config.bm25:
        first = sorted(fused.items(), key=lambda kv: -kv[1])
        extra = feedback.expansion_terms(index, first, qset)
        if extra:
            feedback_terms = list(extra)
            signals["feedback"] = index.bm25({**weights, **{t: w for t, w in extra.items() if t not in weights}}, allowed)
            fused = fuse(signals)
    if not fused:
        return Retrieval([], q_tokens, concepts, expanded, 0.0, False, "nothing matched the question", len(allowed), intent=plan.intent)
    top_fused = max(fused.values())
    max_bm25 = sum(w * index.idf(t) * (K1 + 1) for t, w in weights.items()) or 1.0
    max_sem = max(semantic.values(), default=1.0) or 1.0
    asked_authorities = set(plan.authorities) if config.authority else set()

    # ---- rerank on interpretable features
    hits: list[Hit] = []
    for i, f in fused.items():
        p = index.passages[i]
        matched = content & p.token_set
        # a term is also covered when the passage mentions the concept that term named ("kicks" ~ "baby's movements")
        covered = frozenset(matched | {t for c in q_concepts & graph.passage_concepts[i] for t in spans[c] if t in content})
        coverage = len(matched) / len(content)  # ranking stays literal; concept-level coverage only decides sufficiency
        concept_cov = len(q_concepts & graph.passage_concepts[i]) / len(q_concepts) if q_concepts else 0.0
        prox = _proximity(p.tokens, matched)
        evidence = EVIDENCE_WEIGHT.get(str(p.meta.get("evidence_level", "")).lower(), 0.5)
        quality = float(p.meta.get("readability", 1.0))
        passage_stage = p.meta.get("stage")
        stage_fit = 1.0 if profile.stage and passage_stage == profile.stage else 0.0
        title_cov = len(content & frozenset(tokens(str(p.meta.get("title", ""))))) / len(content)
        sem = semantic.get(i, 0.0) / max_sem
        struct = structure.get(i, 0.0)
        score = (
            0.36 * f / top_fused
            + 0.17 * coverage
            + 0.08 * prox
            + 0.10 * concept_cov
            + 0.06 * title_cov
            + 0.05 * sem
            + 0.07 * struct
            + 0.04 * evidence
            + 0.03 * quality
            + 0.02 * stage_fit
        )
        if profile.stage and passage_stage not in (None, "all", profile.stage):
            score *= 0.93  # written for another stage: still reachable, just less preferred
        if p.meta.get("topic") == "nutrient_profile" and not any(graph.concepts[c].type == "food" for c in q_concepts):
            score *= 0.7  # "how much iron do I need?" is about intake guidance, not about one food's label
        traditional = p.meta.get("domain") == "ayurveda" or p.meta.get("source_type") == "traditional"
        if qset & TRADITIONAL_CUES:
            if not traditional:
                score *= 0.65
        elif traditional:
            # Nobody asked for the classical view. The book is 85% of all passages and its OCR is full of everyday
            # words, so without this prior it would out-rank modern guidance on questions like "constipation".
            score *= 0.6 + 0.15 * quality
        cited = [a for a in asked_authorities if a in p.meta.get("authorities", {})]
        if asked_authorities:
            score *= 1.25 if cited else 0.85  # "what does Caraka say": prefer passages that cite him
        if profile.diet in {"vegetarian", "vegan"} and (graph.passage_concepts[i] & _ANIMAL_CONCEPTS) and not (
            q_concepts & _ANIMAL_CONCEPTS
        ):
            score *= 0.85  # the question is not about meat/fish, so prefer passages that fit this diet
        hits.append(
            Hit(
                idx=i, id=p.id, meta=p.meta, text=p.text, score=score,
                bm25=bm25.get(i, 0.0) / max_bm25, ngram=ngram.get(i, 0.0), concept=concept_cov,
                semantic=sem, structure=struct, graph=graph_score.get(i, 0.0),
                coverage=coverage, proximity=prox, covered=covered,
                matched_terms=sorted(matched), matched_concepts=sorted(q_concepts & graph.passage_concepts[i]),
                authorities=cited,
            )
        )
    hits.sort(key=lambda h: -h.score)
    pool = hits[: CANDIDATES]

    # ---- diversify: MMR with per-source / per-document caps
    chosen: list[Hit] = []
    per_source: dict[str, int] = {}
    per_doc: dict[str, int] = {}
    tables = 0
    remaining = list(pool)
    while remaining and len(chosen) < k:
        best, best_val = None, -math.inf
        for h in remaining:
            if per_source.get(h.meta["source_id"], 0) >= MAX_PER_SOURCE or per_doc.get(h.meta["document_id"], 0) >= MAX_PER_DOCUMENT:
                continue
            if h.meta.get("topic") == "nutrient_profile" and tables >= MAX_NUTRIENT_TABLES:
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
        tables += best.meta.get("topic") == "nutrient_profile"

    # ---- judge
    contributing = [name for name, sc in signals.items() if sc]
    if not chosen:
        return Retrieval([], q_tokens, concepts, expanded, 0.0, False, "no passage survived filtering", len(allowed), intent=plan.intent)
    top = chosen[0]
    max_idf = math.log(1 + (index.size + 0.5) / 0.5)

    def weight(term: str) -> float:  # a word that appears nowhere in the corpus is maximally informative -- and unmatched
        return index.idf(term) if index.df.get(term) else max_idf

    total = sum(weight(t) for t in content) or 1.0
    best_sentence = 0.0
    union: set[str] = set()
    for hit in chosen[:TOP_FOR_EVIDENCE]:
        union |= hit.covered
        for sent in sentences(hit.text) or [hit.text]:
            sent_tokens = tokens(sent)
            sent_covered = content & set(sent_tokens)
            for cid in set(graph.detect(sent_tokens)) & q_concepts:  # same concept, different words
                sent_covered |= spans[cid] & content
            best_sentence = max(best_sentence, sum(weight(t) for t in sent_covered) / total)
    union_cov = sum(weight(t) for t in union) / total
    top_covered = len(top.covered) / len(content)
    confidence = round(min(1.0, 0.40 * min(best_sentence / 0.8, 1.0) + 0.35 * union_cov + 0.25 * top_covered), 3)
    sufficient = (
        top_covered >= MIN_COVERAGE and best_sentence >= MIN_SENTENCE_COVERAGE and union_cov >= MIN_UNION_COVERAGE
    )
    reason = (
        "enough evidence"
        if sufficient
        else (
            f"the closest passages match only part of the question (best sentence {best_sentence:.0%}, "
            f"passages together {union_cov:.0%}, best passage {top_covered:.0%}); not enough to answer reliably"
        )
    )
    return Retrieval(
        chosen, q_tokens, concepts, expanded, confidence, sufficient, reason, len(allowed),
        round(best_sentence, 3), round(union_cov, 3), wants_quantity(query), plan.intent, plan.authorities,
        feedback_terms, activated, [], contributing,
    )
