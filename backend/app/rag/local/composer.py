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
import re
from dataclasses import dataclass, field

from app.rag.local.corpus import Engine
from app.rag.local.retriever import TRADITIONAL_CUES, Hit, Retrieval, UserProfile
from app.rag.local.text import is_prose, sentences, tokens

MODERN_SECTION = "MODERN MEDICAL INFORMATION"
TRADITIONAL_SECTION = "TRADITIONAL/AYURVEDIC INFORMATION"
EVIDENCE_SECTION = "EVIDENCE STATUS"

TRADITIONAL_NOTE = "_Traditional/Ayurvedic text, translated from classical sources. It is not modern clinical evidence._"
MAX_PASSAGES = 4
MAX_SENTENCE_WORDS = 55
RELEVANCE_VS_BEST = 0.7  # a passage must reach this share of the best sentence's score to be quoted
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


MIN_CORPUS_FOR_RARITY = 200
MAX_RARE_RATIO = 0.12  # OCR garbage is made of words that appear nowhere else in the corpus


def _clean_enough(sentence: str, hit: Hit, engine: Engine) -> bool:
    """Extra scrutiny for scanned text: reject sentences full of one-off 'words' or stray glyphs."""
    if not _is_traditional(hit):
        return True
    if any(ch in sentence for ch in "$&|~^_{}[]\\") and not sentence.rstrip().endswith("]"):
        return False
    if sentence.count("(") != sentence.count(")") or sentence.rstrip(" .").endswith(("-", "—", "(", ",")):
        return False  # cut off mid-phrase by the scan or the sentence splitter
    toks = tokens(sentence)
    if not toks:
        return False
    if engine.index.size < MIN_CORPUS_FOR_RARITY:
        return True  # in a tiny corpus every word is rare; the signal only means something at scale
    df = engine.index.df
    rare = sum(1 for t in toks if df.get(t, 0) <= 1) / len(toks)
    return rare <= MAX_RARE_RATIO


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


def _score_sentence(sentence: str, q_idf: dict[str, float], concept_ids: set[str], engine: Engine,
                    title_tokens: frozenset[str] = frozenset(), quantity: bool = False) -> float:
    toks = set(tokens(sentence))
    if not toks:
        return 0.0
    total = sum(q_idf.values()) or 1.0
    # a word in the document's TITLE counts too ("Ragi - Nutrient Profile" answers a question about ragi even if the
    # sentence only says "calcium ~340 mg"), but a little less than a word in the sentence itself
    overlap = sum(w * (1.0 if t in toks else 0.6 if t in title_tokens else 0.0) for t, w in q_idf.items()) / total
    concepts = engine.graph.detect_text(sentence)
    concept_cov = len(concept_ids & set(concepts)) / len(concept_ids) if concept_ids else 0.0
    n = len(sentence.split())
    length_fit = 1.0 if 8 <= n <= 70 else (0.7 if n < 8 else max(0.6, 1 - (n - 70) / 120))  # list-style sentences are fine
    base = (0.6 * overlap + 0.25 * concept_cov) * length_fit + 0.15 * overlap
    if quantity and re.search(r"\d", sentence) and re.search(r"\b(mg|g|kg|mcg|micrograms?|kcal|calories|%|glasses?|portions?|weeks?|months?|days?|hours?|ml)\b", sentence, re.I):
        base += 0.25 * min(overlap * 2, 1.0)  # a stated amount, in a sentence that is on topic
    return base


def _pick(engine: Engine, retrieval: Retrieval, hits: list[Hit]) -> list[Picked]:
    """Choose the sentences that answer the question.

    The top passage always speaks (up to three sentences). Any other passage only contributes if its best sentence is within reach of the best sentence anywhere
    (so a nutrient table that merely mentions "iron" does not sit beside the guideline that actually says
    how much), and then contributes a single sentence.
    """
    q_idf = {t: engine.index.idf(t) for t in retrieval.query_tokens}
    concept_ids = set(retrieval.concepts)
    ranked: list[tuple[Hit, list[tuple[float, str, int]]]] = []
    top_score = hits[0].score if hits else 1.0
    for hit in hits:
        trust = 0.5 + 0.5 * (hit.score / top_score if top_score else 0.0)  # sentences inherit their passage's rank
        title_tokens = frozenset(tokens(str(hit.meta.get("title", ""))))
        scored = sorted(
            ((trust * _score_sentence(s, q_idf, concept_ids, engine, title_tokens, retrieval.quantity_intent), s, n) for n, s in enumerate(sentences(hit.text)) if is_prose(s) and _clean_enough(s, hit, engine)),
            key=lambda t: -t[0],
        )
        if scored:
            ranked.append((hit, scored))
    if not ranked:
        return []
    global_best = max(scored[0][0] for _, scored in ranked)
    picked: list[Picked] = []
    seen: list[frozenset[str]] = []
    for position, (hit, scored) in enumerate(ranked):
        best = scored[0][0]
        # the top-ranked passage always speaks; the others must be close to the best sentence found anywhere
        if best < 0.06 or (position > 0 and (best < 0.12 or best < RELEVANCE_VS_BEST * global_best)):
            continue
        limit = 3 if position == 0 else 1  # the best passage may add up to two more sentences
        follow_up = 0.45 if position == 0 else 1.0
        chosen: list[tuple[int, Picked]] = []
        for score, sentence, order in scored:
            if len(chosen) >= limit or score < 0.06 or (chosen and score < follow_up * best):
                break
            sig = frozenset(tokens(sentence))
            if any(len(sig & other) / max(len(sig | other), 1) > 0.7 for other in seen):
                continue
            seen.append(sig)
            chosen.append((order, Picked(_shorten(sentence), score, hit)))
        picked.extend(p for _, p in sorted(chosen, key=lambda t: t[0]))  # read in the order the source wrote them
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
    asked_for_traditional = bool(set(retrieval.query_tokens) & TRADITIONAL_CUES)
    if traditional and not asked_for_traditional and modern:
        # Modern sources already answer it, and nobody asked for the classical view: leave scanned text out.
        picked = modern
        traditional = []

    # A question that asks for the Ayurvedic view leads with the traditional section; the sections stay separate.
    traditional_first = bool(set(retrieval.query_tokens) & TRADITIONAL_CUES)
    first, second = (traditional, modern) if traditional_first else (modern, traditional)

    # citation numbers by order of appearance in the final text
    order: list[Hit] = []
    for p in first + second:
        if all(h.id != p.hit.id for h in order):
            order.append(p.hit)
    number = {h.id: n for n, h in enumerate(order, start=1)}

    def bullets(items: list[Picked]) -> list[str]:
        return [f"- {p.sentence} [{number[p.hit.id]}]" for p in items]

    topic = _topic_phrase(engine, retrieval.concepts)
    lead = f"Here is what the reviewed sources say about {topic}:" if topic else "Here is what the reviewed sources say:"
    lines: list[str] = []
    both = bool(modern) and bool(traditional)
    modern_block = [f"**{MODERN_SECTION}**", *bullets(modern)]
    traditional_block = [f"**{TRADITIONAL_SECTION}**", *bullets(traditional), TRADITIONAL_NOTE]
    if both:
        lines += [lead, "", *(traditional_block + [""] + modern_block if traditional_first else modern_block + [""] + traditional_block)]
    elif traditional:
        lines += [lead, "", *bullets(traditional), TRADITIONAL_NOTE]
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

    used = order  # sources shown are exactly the sources cited, in citation order
    quotes: dict[str, list[str]] = {}
    for p in picked:
        quotes.setdefault(p.hit.id, []).append(p.sentence)
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
                "quotes": quotes.get(h.id, []),
                "source": h.meta.get("source_title") or h.meta.get("source_name"),
                "url": h.meta.get("url"),
            }
            for h in used
        ],
    }
    return Composed(text="\n".join(lines).strip(), used=used, confidence=retrieval.confidence, notes=notes, trace=trace)
