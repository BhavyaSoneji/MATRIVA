"""Answer composition without a language model: select, order and cite the best sentences.

The answer is built ONLY from sentences that already exist in approved passages, so it cannot invent a
fact. What the composer adds is judgement about which sentences answer the question:

    each retrieved passage -> split into sentences -> score every sentence for this question
    (idf-weighted term overlap, concept coverage, sensible length) -> keep the best one or two per passage
    -> drop near-duplicates -> group modern vs. traditional (they are never blended)
    -> number citations in order of appearance -> add personalised notes (stage, allergies, diet)

Citations are numbered [1], [2] ... in the order they first appear, and the passages are returned in that
same order, so the numbers line up with the citation list shown under the answer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.rag.local.corpus import Engine
from app.rag.local.retriever import Hit, Retrieval, UserProfile
from app.rag.local.text import sentences, tokens

MODERN_SECTION = "MODERN MEDICAL INFORMATION"
TRADITIONAL_SECTION = "TRADITIONAL/AYURVEDIC INFORMATION"
EVIDENCE_SECTION = "EVIDENCE STATUS"

MAX_PASSAGES = 4
MAX_SENTENCE_WORDS = 55
_STAGE_NAME = {"first_trimester": "first trimester", "second_trimester": "second trimester", "third_trimester": "third trimester"}


@dataclass
class Picked:
    sentence: str
    score: float
    hit: Hit


@dataclass
class Composed:
    text: str
    used: list[Hit]  # passages in citation order ([1] is used[0])
    confidence: float
    notes: list[str] = field(default_factory=list)
    trace: dict = field(default_factory=dict)


def _is_traditional(hit: Hit) -> bool:
    return hit.meta.get("domain") == "ayurveda" or hit.meta.get("source_type") == "traditional"


def _shorten(sentence: str) -> str:
    words = sentence.split()
    if len(words) <= MAX_SENTENCE_WORDS:
        return sentence
    cut = " ".join(words[:MAX_SENTENCE_WORDS])
    for stop in ("; ", ", ", " and ", " which "):  # prefer ending at a natural clause break
        pos = cut.rfind(stop)
        if pos > len(cut) * 0.6:
            cut = cut[:pos]
            break
    return cut.rstrip(" ,;:") + "…"


def _score_sentence(sentence: str, q_idf: dict[str, float], concept_ids: set[str], engine: Engine) -> float:
    toks = set(tokens(sentence))
    if not toks:
        return 0.0
    total = sum(q_idf.values()) or 1.0
    overlap = sum(w for t, w in q_idf.items() if t in toks) / total
    concepts = engine.graph.detect_text(sentence)
    concept_cov = len(concept_ids & set(concepts)) / len(concept_ids) if concept_ids else 0.0
    n = len(sentence.split())
    length_fit = 1.0 if 8 <= n <= 40 else (0.7 if n < 8 else max(0.5, 1 - (n - 40) / 80))
    return (0.6 * overlap + 0.25 * concept_cov) * length_fit + 0.15 * overlap


def _pick(engine: Engine, retrieval: Retrieval, hits: list[Hit]) -> list[Picked]:
    q_idf = {t: engine.index.idf(t) for t in retrieval.query_tokens}
    concept_ids = set(retrieval.concepts)
    picked: list[Picked] = []
    seen: list[frozenset[str]] = []
    for hit in hits:
        scored = sorted(
            ((_score_sentence(s, q_idf, concept_ids, engine), s) for s in sentences(hit.text)), key=lambda t: -t[0]
        )
        if not scored:
            continue
        best = scored[0][0]
        taken = 0
        for score, sentence in scored:
            if taken >= 2 or score < 0.12 or (taken >= 1 and score < 0.8 * best):
                break
            sig = frozenset(tokens(sentence))
            if any(len(sig & other) / max(len(sig | other), 1) > 0.7 for other in seen):
                continue
            seen.append(sig)
            picked.append(Picked(_shorten(sentence), score, hit))
            taken += 1
    return picked


def _topic_phrase(engine: Engine, concepts: list[str]) -> str:
    labels = [engine.graph.concepts[c].label for c in concepts if engine.graph.concepts[c].type != "stage"][:3]
    if not labels:
        return ""
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]


def compose(engine: Engine, retrieval: Retrieval, profile: UserProfile | None = None) -> Composed:
    profile = profile or UserProfile()
    hits = retrieval.hits[:MAX_PASSAGES]
    picked = _pick(engine, retrieval, hits)
    modern = [p for p in picked if not _is_traditional(p.hit)]
    traditional = [p for p in picked if _is_traditional(p.hit)]

    # citation numbers by order of appearance in the final text
    order: list[Hit] = []
    for p in modern + traditional:
        if all(h.id != p.hit.id for h in order):
            order.append(p.hit)
    number = {h.id: n for n, h in enumerate(order, start=1)}

    def bullets(items: list[Picked]) -> list[str]:
        return [f"- {p.sentence} [{number[p.hit.id]}]" for p in items]

    topic = _topic_phrase(engine, retrieval.concepts)
    lead = f"Here is what the reviewed sources say about {topic}:" if topic else "Here is what the reviewed sources say:"
    lines: list[str] = []
    both = bool(modern) and bool(traditional)
    if both:
        lines += [lead, "", f"**{MODERN_SECTION}**", *bullets(modern), "", f"**{TRADITIONAL_SECTION}**", *bullets(traditional)]
        lines.append("_Traditional text, translated from classical sources. It is not modern clinical evidence._")
    elif traditional:
        lines += [lead, "", *bullets(traditional)]
        lines.append("_This is traditional/Ayurvedic text, translated from classical sources — not modern clinical evidence._")
    else:
        lines += [lead, "", *bullets(modern)]

    # ---- personalisation, all deterministic
    notes: list[str] = []
    stage_hits = [h for h in order if h.meta.get("stage") == profile.stage] if profile.stage else []
    if stage_hits:
        notes.append(f"Some of this is specific to your stage ({_STAGE_NAME.get(profile.stage, profile.stage)}).")
    chosen_tokens = {t for p in picked for t in tokens(p.sentence)}
    for allergy in profile.allergies:
        if set(tokens(allergy)) and set(tokens(allergy)) <= chosen_tokens:
            notes.append(f"Heads up: this mentions {allergy}, which you listed as an allergy — please avoid it and ask your doctor.")
    if profile.diet in {"vegetarian", "vegan"} and chosen_tokens & {"meat", "chicken", "fish", "liver", "mutton"}:
        notes.append(f"Some of this refers to animal foods; you eat a {profile.diet} diet, so ask me for plant-based options.")
    if notes:
        lines += ["", *[f"> {n}" for n in notes]]

    # ---- evidence status
    levels: dict[str, int] = {}
    for h in order:
        lvl = str(h.meta.get("evidence_level", "unknown")).replace("_", " ")
        levels[lvl] = levels.get(lvl, 0) + 1
    match = "strong" if retrieval.confidence >= 0.65 else "moderate" if retrieval.confidence >= 0.45 else "partial"
    status = ", ".join(f"{n} {lvl}" for lvl, n in levels.items())
    lines += ["", f"**{EVIDENCE_SECTION}**", f"{match.capitalize()} match from {len(order)} reviewed passage{'s' if len(order) != 1 else ''} ({status})."]
    lines += [
        "",
        "This is educational information, not a diagnosis or a substitute for your maternity-care professional.",
    ]

    used = order + [h for h in retrieval.hits if all(h.id != o.id for o in order)]
    trace = {
        "engine": "local",
        "confidence": retrieval.confidence,
        "concepts": [engine.graph.concepts[c].label for c in retrieval.concepts],
        "related_concepts": [engine.graph.concepts[c].label for c in list(retrieval.expanded)[:5]],
        "query_terms": retrieval.query_tokens,
        "passages_searched": retrieval.pool,
        "passages": [
            {
                "citation": number.get(h.id),
                "title": h.meta.get("title"),
                "domain": h.meta.get("domain"),
                "locator": h.meta.get("locator"),
                "score": round(h.score, 3),
                "bm25": round(h.bm25, 3),
                "ngram": round(h.ngram, 3),
                "coverage": round(h.coverage, 3),
                "matched_terms": h.matched_terms[:8],
                "matched_concepts": [engine.graph.concepts[c].label for c in h.matched_concepts],
            }
            for h in used
        ],
    }
    return Composed(text="\n".join(lines).strip(), used=used, confidence=retrieval.confidence, notes=notes, trace=trace)
