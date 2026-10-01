"""The advanced retrieval signals, one by one: semantic space, feedback, graph activation, structure, authorities,
query understanding, compound questions and the Config switches used by the ablation study."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

from app.rag.local import authorities, feedback
from app.rag.local.corpus import Engine
from app.rag.local.graph import KnowledgeGraph
from app.rag.local.index import LocalIndex, Passage
from app.rag.local.retriever import DEFAULT, Config, UserProfile, search
from app.rag.local.text import stem, tokens
from app.rag.local.understanding import analyze, authorities_in, intent_of, split_compound


def P(pid: str, text: str, **meta) -> Passage:
    base = {"title": f"Doc {pid}", "document_id": pid, "source_id": pid, "domain": "modern_medical",
            "evidence_level": "supported", "stage": None, "region": None, "source_type": "government"}
    return Passage(id=pid, text=text, meta={**base, **meta})


def _topic_corpus() -> list[Passage]:
    """30 passages: anaemia, nausea and filler. Anaemia passages co-use 'haemoglobin' and 'tablets' with 'anaemia'."""
    ps = []
    for i in range(8):
        ps.append(P(f"an{i}", f"Anaemia means low haemoglobin; iron tablets raise haemoglobin and treat anaemia in pregnancy case {i}."))
    ps.append(P("an_only", "Anaemia in pregnancy should be treated by a doctor after a blood test."))
    for i in range(8):
        ps.append(P(f"na{i}", f"Morning sickness brings nausea and vomiting; ginger and small meals ease the nausea in early pregnancy case {i}."))
    for i in range(22):
        ps.append(P(f"f{i}", f"Antenatal visit number {i} includes weighing, blood pressure and a scan according to the schedule."))
    return ps


# ------------------------------------------------------------------ stemming fix that the concepts depend on
def test_plural_and_singular_meet_after_stemming() -> None:
    assert stem("exercises") == stem("exercise") == stem("exercising") or stem("exercises") == stem("exercise")
    assert stem("tablets") == stem("tablet") and stem("classes") == stem("class")
    assert stem("illness") == "illness" and stem("uterus") == "uterus" and stem("breastfeeding") == stem("breastfeed")


# ------------------------------------------------------------------ semantic space (LSA)
def test_semantic_space_ranks_the_topic_cluster_and_is_deterministic() -> None:
    idx = LocalIndex(_topic_corpus())
    assert idx.semantic.ready and idx.semantic.doc_vectors.shape[0] == idx.size
    first = idx.semantic.scores(tokens("low haemoglobin"))
    again = idx.semantic.scores(tokens("low haemoglobin"))
    assert first == again  # no randomness for a corpus this size
    ranked = sorted(first, key=lambda i: -first[i])
    assert all(idx.passages[i].id.startswith("an") for i in ranked[:8])  # the anaemia cluster, not nausea or filler
    assert not any(idx.passages[i].id.startswith("na") for i in first)


def test_semantic_space_is_off_for_tiny_corpora_and_never_crashes() -> None:
    idx = LocalIndex([P("a", "iron and calcium"), P("b", "ginger for nausea")])
    assert not idx.semantic.ready and idx.semantic.scores(["iron"]) == {}


# ------------------------------------------------------------------ pseudo-relevance feedback
def test_feedback_adds_vocabulary_the_best_passages_use() -> None:
    idx = LocalIndex(_topic_corpus())
    ranked = [(i, 1.0) for i, p in enumerate(idx.passages) if p.id.startswith("an") and p.id != "an_only"]
    terms = feedback.expansion_terms(idx, ranked, {"anaemia"})
    assert "haemoglobin" in " ".join(terms) or any(t.startswith("haemoglob") for t in terms)
    assert "anaemia" not in terms and all(0 < w <= feedback.EXPANSION_WEIGHT + 1e-9 for w in terms.values())
    assert feedback.expansion_terms(idx, [], set()) == {}


# ------------------------------------------------------------------ graph activation
def test_activation_spreads_to_related_concepts_and_sums_to_one() -> None:
    docs = ["iron anaemia folic acid", "iron anaemia haemoglobin", "iron anaemia tablets", "calcium milk ragi", "calcium milk curd",
            "ginger nausea vomiting", "ginger nausea morning sickness"]
    g = KnowledgeGraph.build([tokens(d) for d in docs])
    a = g.activation({"iron": 1.0})
    assert abs(sum(a.values()) - 1.0) < 1e-6
    assert a["iron"] == max(a.values()) and a.get("anaemia", 0) > a.get("nausea", 0) and a.get("anaemia", 0) > 0
    assert g.activation({}) == {} and g.activation({"not_a_concept": 1.0}) == {}


# ------------------------------------------------------------------ structure
def test_passages_inherit_their_section_title_score() -> None:
    ps = [P(f"s{i}", f"damaged scan text {i} xqzv wlrk", document_id="book", section="Monthwise dietary regimen", chapter_title="Antenatal care",
            title="Book chapter 5") for i in range(3)] + [P("o", "unrelated passage about ginger", document_id="other", title="Ginger")]
    idx = LocalIndex(ps)
    scores = idx.structure_scores({"monthwis", "dietari", "regimen"})
    assert set(scores) == {0, 1, 2} and all(v >= 0.34 for v in scores.values())
    assert idx.structure_scores(set()) == {}


# ------------------------------------------------------------------ authorities
def test_authority_lexicon_matches_the_ingestion_pipeline() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ingestion"))
    from pipelines import book_structure

    assert set(authorities.AUTHORITIES) == set(book_structure.AUTHORITIES)
    text = "Caraka and Suéruta agree; Vagbhata I differs; Kaéyapa too"
    assert authorities.detect(text) == book_structure.count_authorities(text)


def test_question_naming_an_authority_prefers_passages_that_cite_him() -> None:
    caraka = P("c", "Caraka advises milk and ghee in the later months of pregnancy for strength.", domain="ayurveda", source_type="traditional", evidence_level="traditional")
    other = P("o", "Dalhana advises milk and ghee in the later months of pregnancy for strength.", domain="ayurveda", source_type="traditional", evidence_level="traditional")
    eng = Engine([other, caraka] + _topic_corpus()[:24])
    r = search(eng, "What does Caraka say about milk and ghee in pregnancy?")
    assert r.authorities == ["Caraka"] and r.hits[0].id == "c" and r.hits[0].authorities == ["Caraka"]
    off = search(eng, "What does Caraka say about milk and ghee in pregnancy?", config=replace(DEFAULT, authority=False))
    assert off.hits[0].authorities == []  # the boost is what put him first


# ------------------------------------------------------------------ understanding
@pytest.mark.parametrize(
    "question, intent",
    [("What is dauhrda?", "definition"), ("How much iron do I need?", "quantity"), ("Is coffee safe?", "safety"),
     ("How do I ease back pain?", "how_to"), ("Which foods are rich in iron?", "list"), ("difference between pitta and kapha", "comparison"),
     ("hello there friend", "general")],
)
def test_intents(question: str, intent: str) -> None:
    assert intent_of(question) == intent


def test_authorities_in_question() -> None:
    assert authorities_in("What did Sushruta and Charaka say?") == ["Caraka", "Susruta"]
    assert authorities_in("What is iron?") == []


def test_compound_questions_split_only_when_halves_are_never_discussed_together() -> None:
    docs = ["iron anaemia folic acid", "iron anaemia tablets", "calcium milk ragi", "calcium milk curd"]
    g = KnowledgeGraph.build([tokens(d) for d in docs])
    assert split_compound("iron and calcium", g) == ["iron", "calcium"]
    g2 = KnowledgeGraph.build([tokens(d) for d in docs + ["iron and calcium supplements together", "iron calcium zinc"]])
    assert split_compound("iron and calcium", g2) == []  # a passage discusses both: one question
    assert analyze("pitta and kapha difference", g).sub_queries == []  # comparisons are never split


def test_compound_question_retrieves_each_half() -> None:
    eng = Engine(_topic_corpus() + [P("ca", "Calcium from milk and ragi builds the baby's bones in pregnancy.")])
    r = search(eng, "anaemia and calcium")
    ids = [h.id for h in r.hits]
    assert r.sub_queries and any(i.startswith("an") for i in ids) and "ca" in ids


# ------------------------------------------------------------------ config switches
def test_every_signal_can_be_switched_off_and_the_engine_still_answers() -> None:
    eng = Engine(_topic_corpus())
    for name in ("semantic", "structure", "graph", "feedback", "concept", "ngram", "authority", "decompose"):
        r = search(eng, "how is anaemia treated", config=replace(DEFAULT, **{name: False}))
        assert r.hits and r.hits[0].id.startswith("an"), name
    lexical = Config(semantic=False, structure=False, graph=False, feedback=False, concept=False, authority=False, decompose=False)
    assert search(eng, "how is anaemia treated", config=lexical).hits[0].id.startswith("an")


def test_retrieval_reports_which_signals_fired(client=None) -> None:
    eng = Engine(_topic_corpus())
    r = search(eng, "morning sickness and vomiting", profile=UserProfile())
    assert {"bm25", "ngram", "semantic"} <= set(r.signals) and r.intent in {"general", "how_to"}
