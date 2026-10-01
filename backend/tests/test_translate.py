from app.rag.translate import glossary_translate, to_english_query


def test_glossary_maps_hindi_and_gujarati_to_english_terms() -> None:
    assert set(glossary_translate("गर्भावस्था में आयरन वाला खाना").split()) == {"pregnancy", "iron", "food", "diet"}
    assert "yoga" in glossary_translate("क्या योग करना सुरक्षित है")
    assert "milk" in glossary_translate("ગર્ભાવસ્થામાં દૂધ")
    assert glossary_translate("hello there") is None


def test_longest_term_wins() -> None:
    out = glossary_translate("पहली तिमाही में क्या खाना")
    assert out.startswith("first trimester") and "food" in out


def test_english_is_left_alone_unless_user_writes_hinglish() -> None:
    assert to_english_query("What should I eat?") == "What should I eat?"
    assert to_english_query("khana kya khaun", language="hi") == "food diet"
    assert to_english_query("khana kya khaun", language="en") == "khana kya khaun"


def test_llm_translation_wins_over_glossary_and_failure_falls_back() -> None:
    assert to_english_query("मुझे आयरन चाहिए", translator=lambda t: "I need iron") == "I need iron"
    assert to_english_query("मुझे आयरन चाहिए", translator=lambda t: None) == "iron"
    assert to_english_query("कुछ भी नहीं", translator=lambda t: None) == "कुछ भी नहीं"  # nothing matched -> unchanged


def test_hindi_chat_question_is_searched_in_english(client, auth_headers, monkeypatch) -> None:
    import app.services.chat as chat_module

    seen: list[str] = []
    real = chat_module.answer_question

    def spy(db, query, **kwargs):
        seen.append(query)
        return real(db, query, **kwargs)

    monkeypatch.setattr(chat_module, "answer_question", spy)
    res = client.post("/chat", headers=auth_headers, json={"message": "गर्भावस्था में एंटेनेटल चेकअप का शेड्यूल क्या है", "language": "hi"}).json()
    assert res["safety_status"] != "urgent_escalation"
    assert {"pregnancy", "antenatal", "schedule"} <= set(seen[-1].split())
