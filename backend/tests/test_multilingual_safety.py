import pytest

from app.models import RiskLevel
from app.safety.classifier import classify_query


@pytest.mark.parametrize(
    "query",
    [
        "मुझे बहुत ब्लीडिंग हो रही है",
        "बच्चा हिल नहीं रहा है, क्या करूं",
        "मेरे पेट में तेज दर्द है",
        "mujhe tez sir dard hai aur dhundhla dikh raha hai",
        "baby hil nahi raha kal se",
        "મારા બાળક હલતું નથી",
        "પેટમાં તીવ્ર દુખાવો થાય છે",
        "मुझे सांस लेने में तकलीफ है",
    ],
)
def test_urgent_symptoms_in_hindi_hinglish_gujarati_escalate(query: str) -> None:
    decision = classify_query(query, [])
    assert decision.risk == RiskLevel.URGENT_ESCALATION, query


@pytest.mark.parametrize(
    "query",
    ["गर्भावस्था में क्या खाना चाहिए", "ragi khana theek hai kya", "ગર્ભાવસ્થામાં શું ખાવું જોઈએ"],
)
def test_ordinary_questions_in_other_languages_are_not_escalated(query: str) -> None:
    assert classify_query(query, []).risk == RiskLevel.SAFE_GENERAL


def test_chat_short_circuits_a_hindi_emergency(client, auth_headers) -> None:
    res = client.post("/chat", headers=auth_headers, json={"message": "मुझे बहुत ब्लीडिंग हो रही है", "language": "hi"})
    body = res.json()
    assert body["safety_status"] == "urgent_escalation"
    assert body["sources"] == [] and body["suggestions"] == []
