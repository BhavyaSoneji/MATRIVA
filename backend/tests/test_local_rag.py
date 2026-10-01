"""The offline RAG engine: text processing, graph, hybrid retrieval, composition and chat integration."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.models import KnowledgeDocument
from app.rag.local.composer import EVIDENCE_SECTION, MODERN_SECTION, TRADITIONAL_SECTION, compose
from app.rag.local.corpus import Engine, get_engine
from app.rag.local.graph import KnowledgeGraph
from app.rag.local.index import Passage
from app.rag.local.retriever import UserProfile, search
from app.rag.local.text import char_ngrams, fold, sentences, stem, tokens


def passage(pid: str, text: str, *, domain="modern_medical", source=None, level="supported", stage=None, title=None, **meta) -> Passage:
    return Passage(
        id=pid, text=text,
        meta={"title": title or f"Doc {pid}", "document_id": pid, "source_id": source or pid, "domain": domain,
              "evidence_level": level, "stage": stage, "region": None, "source_type": "traditional" if domain == "ayurveda" else "government",
              **meta},
    )


CORPUS = [
    passage("iron", "Iron deficiency anaemia is common in pregnancy. WHO advises daily iron and folic acid supplements, 30-60 mg of iron and 400 micrograms of folic acid. Lentils, spinach and jaggery are iron-rich foods."),
    passage("ragi", "Ragi is a millet very rich in calcium. It is commonly eaten in south India and supports the bones of the baby.", domain="nutrition"),
    passage("nausea", "Nausea and vomiting in early pregnancy usually clears by weeks 16 to 20. Ginger and small frequent meals may help morning sickness.", stage="first_trimester"),
    passage("milk", "Milk and ghee should be given to the pregnant woman in the later months. Garbhini paricharya describes a monthly regimen that nourishes the fetus.", domain="ayurveda", level="traditional", source="book"),
    passage("liver", "Avoid liver and liver products in pregnancy because they contain very high levels of vitamin A which can harm the baby."),
]


@pytest.fixture(scope="module")
def engine() -> Engine:
    return Engine(CORPUS)


# ------------------------------------------------------------------ text
def test_fold_strips_sanskrit_diacritics_and_stemming_is_consistent() -> None:
    assert fold("Kṣīra Śatāvarī") == "ksira satavari"
    assert stem("breastfeeding") == stem("breastfeed") == "breastfeed"
    assert stem("illness") == "illness" and stem("uterus") == "uterus"
    assert tokens("What should pregnant women eat?") == ["pregnant", "woman", "food"]


def test_char_ngrams_survive_ocr_typos() -> None:
    assert len(set(char_ngrams("woman")) & set(char_ngrams("wornan"))) >= 2


def test_sentence_splitter_keeps_abbreviations() -> None:
    out = sentences("Milk is good, i.e. nourishing. Dr. Sharma says so. It helps the fetus grow well.")
    assert out[0] == "Milk is good, i.e. nourishing." and len(out) == 3


# ------------------------------------------------------------------ graph
def test_graph_detects_multiword_concepts_and_links_what_co_occurs(engine: Engine) -> None:
    # an edge needs at least two passages mentioning both concepts, so it cannot come from a one-off mention
    g = KnowledgeGraph.build([p.tokens for p in CORPUS] + [tokens("Iron tablets treat anaemia in pregnancy"), tokens("Low iron causes anaemia")])
    assert g.detect_text("iron and folic acid for morning sickness") == ["iron", "folate", "nausea"]
    assert g.detect_text("is ragi okay") == ["ragi"]
    assert "millet" in g.expand(["ragi"])  # is-a hierarchy widens the search
    assert any(other == "anaemia" for other, _, _ in g.neighbors("iron"))  # edge came from a passage mentioning both
    sub = g.subgraph(["iron"])
    assert {"id": "iron", "label": "Iron"}.items() <= {k: sub["nodes"][0][k] for k in ("id", "label")}.items()
    assert all(e["source"] in {n["id"] for n in sub["nodes"]} for e in sub["edges"])


def test_graph_edges_are_normalised_pmi_between_zero_and_one(engine: Engine) -> None:
    assert all(0 < w <= 1 for w, _ in engine.graph.edges.values())


def test_graph_can_be_built_from_nothing() -> None:
    assert KnowledgeGraph.build([]).stats()["edges"] == 0


# ------------------------------------------------------------------ retrieval
@pytest.mark.parametrize(
    "question, expected",
    [
        ("how much iron should I take for anaemia?", "iron"),
        ("is ragi good for calcium", "ragi"),
        ("what helps with morning sickness", "nausea"),
        ("can I eat liver", "liver"),
        ("what does ayurveda say about milk and ghee", "milk"),
    ],
)
def test_right_passage_ranks_first(engine: Engine, question: str, expected: str) -> None:
    r = search(engine, question)
    assert r.sufficient and r.hits[0].id == expected


def test_ocr_typo_still_finds_the_passage(engine: Engine) -> None:
    assert search(engine, "calcum in ragi").hits[0].id == "ragi"


@pytest.mark.parametrize("question", ["best programming language", "how do I train a dog", "capital of France", ""])
def test_unrelated_questions_are_judged_insufficient(engine: Engine, question: str) -> None:
    r = search(engine, question)
    assert not r.sufficient and r.reason


def test_stage_filter_and_fallback(engine: Engine) -> None:
    r = search(engine, "morning sickness", profile=UserProfile(stage="third_trimester"))
    assert r.hits  # a filter must never silently empty the result when the corpus has candidates
    assert search(engine, "morning sickness", profile=UserProfile(stage="first_trimester")).hits[0].id == "nausea"


def test_per_source_cap_keeps_results_diverse() -> None:
    book = [passage(f"b{i}", f"The pregnant woman should take milk and ghee in month {i} according to the regimen.",
                    domain="ayurveda", source="book", title=f"Section {i}", level="traditional") for i in range(8)]
    eng = Engine(book + [passage("mod", "Milk is a source of calcium and protein for the pregnant woman.")])
    ids = [h.id for h in search(eng, "milk for the pregnant woman", k=6).hits]
    assert sum(1 for i in ids if i.startswith("b")) <= 3 and "mod" in ids


def test_vegetarian_diet_prefers_plant_passages() -> None:
    eng = Engine([
        passage("meat", "Chicken and fish are rich sources of iron and protein for pregnant women."),
        passage("veg", "Lentils, spinach and jaggery are rich sources of iron and protein for pregnant women."),
    ])
    veg = search(eng, "rich sources of iron and protein", profile=UserProfile(diet="vegetarian"))
    assert veg.hits[0].id == "veg"


# ------------------------------------------------------------------ composition
def test_answer_is_extractive_cited_and_ends_with_evidence_status(engine: Engine) -> None:
    r = search(engine, "how much iron and folic acid should I take?")
    out = compose(engine, r)
    assert "30-60 mg of iron" in out.text and "[1]" in out.text and EVIDENCE_SECTION in out.text
    assert out.used[0].id == "iron"
    for line in out.text.splitlines():  # every bullet is a real sentence from the corpus
        if line.startswith("- "):
            body = line[2:].rsplit(" [", 1)[0].rstrip("…")
            assert any(body in p.text for p in CORPUS)


def test_modern_and_traditional_are_never_blended(engine: Engine) -> None:
    out = compose(engine, search(engine, "milk and calcium for the pregnant woman"))
    if TRADITIONAL_SECTION in out.text:
        assert MODERN_SECTION in out.text and out.text.index(MODERN_SECTION) < out.text.index(TRADITIONAL_SECTION)
    trad = compose(engine, search(engine, "ayurveda milk ghee garbhini paricharya"))
    assert "traditional" in trad.text.lower() and "not modern clinical evidence" in trad.text


def test_allergy_and_diet_notes_are_deterministic(engine: Engine) -> None:
    r = search(engine, "which iron rich foods like lentils and spinach", profile=UserProfile(allergies=["lentils"]))
    out = compose(engine, r, UserProfile(allergies=["lentils"]))
    assert "lentils, which you listed as an allergy" in out.text


def test_citation_numbers_follow_order_of_appearance(engine: Engine) -> None:
    out = compose(engine, search(engine, "iron anaemia and milk ghee regimen in pregnancy"))
    nums = [int(n) for line in out.text.splitlines() if line.startswith("- ") for n in line.rsplit("[", 1)[1].rstrip("]").split(",")]
    assert nums == sorted(nums) and nums[0] == 1


def test_trace_explains_the_retrieval(engine: Engine) -> None:
    trace = compose(engine, search(engine, "iron for anaemia")).trace
    assert trace["engine"] == "local" and "Iron" in trace["concepts"]
    assert trace["passages"][0]["matched_terms"] and trace["passages_searched"] == len(CORPUS)


# ------------------------------------------------------------------ chat integration (no network, no keys)
def _approve_seed(client: TestClient, admin_headers: dict[str, str]) -> None:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import scripts.ingest_real_knowledge as ingest

    with SessionLocal() as db:
        ingest.ingest_seed_yaml(db, api_key=None, dry_run=False)
        ids = [d.id for d in db.query(KnowledgeDocument).all()]
    assert client.post("/admin/documents/bulk-approve", headers=admin_headers, json={"ids": ids}).status_code == 200


def test_chat_answers_from_approved_documents_with_a_trace(client: TestClient, admin_headers, auth_headers) -> None:
    _approve_seed(client, admin_headers)
    res = client.post("/chat", headers=auth_headers, json={"message": "How much iron is in lentils?"}).json()
    assert res["safety_status"] == "safe_general"
    assert "Lentils" in res["answer"] and "[1]" in res["answer"]
    assert res["evidence"]["engine"] == "local" and res["evidence"]["trace"]["passages"]
    assert res["citations"] and res["sources"]


def test_chat_refuses_when_the_knowledge_base_has_nothing_relevant(client: TestClient, admin_headers, auth_headers) -> None:
    _approve_seed(client, admin_headers)
    res = client.post("/chat", headers=auth_headers, json={"message": "What is the best programming language?"}).json()
    assert res["citations"] == [] and "enough currently reviewed information" in res["answer"]


def test_pending_documents_are_invisible_to_the_local_engine(client: TestClient, auth_headers) -> None:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import scripts.ingest_real_knowledge as ingest

    with SessionLocal() as db:
        ingest.ingest_seed_yaml(db, api_key=None, dry_run=False)
        assert get_engine(db).index.size == 0
    res = client.post("/chat", headers=auth_headers, json={"message": "How much iron is in lentils?"}).json()
    assert res["citations"] == []


def test_index_rebuilds_when_a_document_is_approved(client: TestClient, admin_headers) -> None:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import scripts.ingest_real_knowledge as ingest

    with SessionLocal() as db:
        ingest.ingest_seed_yaml(db, api_key=None, dry_run=False)
        assert get_engine(db).index.size == 0
        ids = [d.id for d in db.query(KnowledgeDocument).limit(3).all()]
    client.post("/admin/documents/bulk-approve", headers=admin_headers, json={"ids": ids})
    with SessionLocal() as db:
        assert get_engine(db).index.size == 3


def test_stream_emits_line_deltas_that_concatenate_to_the_final_answer(client: TestClient, admin_headers, auth_headers) -> None:
    import json

    _approve_seed(client, admin_headers)
    body = client.post("/chat/stream", headers=auth_headers, json={"message": "How much iron is in lentils?"}).text
    frames = [(b.split("\n")[0][7:], json.loads(b.split("\n")[1][5:])) for b in body.strip().split("\n\n")]
    deltas = "".join(d["text"] for e, d in frames if e == "delta")
    final = next(d for e, d in frames if e == "final")
    assert len([1 for e, _ in frames if e == "delta"]) > 3 and deltas == final["answer"] and final["corrected"] is False


def test_no_external_provider_is_used_in_local_mode(client: TestClient, admin_headers, auth_headers, monkeypatch) -> None:
    import app.llm.groq_client as groq_client
    import app.rag.embeddings as embeddings

    def boom(*a, **k):
        raise AssertionError("an external provider was called in local mode")

    monkeypatch.setattr(groq_client, "Groq", boom)
    monkeypatch.setattr(embeddings, "embed_text", boom)
    monkeypatch.setattr("app.rag.retrieval.embed_text", boom)
    _approve_seed(client, admin_headers)
    assert client.post("/chat", headers=auth_headers, json={"message": "गर्भावस्था में आयरन कहाँ से मिलेगा", "language": "hi"}).status_code == 200


def test_building_the_index_is_fast() -> None:
    big = [passage(f"p{i}", f"Pregnant woman diet iron calcium milk passage number {i} about food and nutrition " * 8) for i in range(1500)]
    t0 = time.perf_counter()
    eng = Engine(big)
    build = time.perf_counter() - t0
    t1 = time.perf_counter()
    search(eng, "iron in milk for the pregnant woman")
    assert build < 8 and time.perf_counter() - t1 < 1.0
