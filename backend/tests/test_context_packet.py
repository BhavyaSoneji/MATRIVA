import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.context_packet import build_context_packet  # noqa: E402
from app.rag.reranking import UserContext  # noqa: E402
from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeChunk  # noqa: E402


def make_chunk(chunk_id: str, content: str, document_id: str = "doc-1") -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        source_id="src-1",
        domain=Domain.NUTRITION,
        evidence_level=EvidenceLevel.SUPPORTED,
        content=content,
        chunk_index=0,
    )


def test_packet_includes_all_five_sections() -> None:
    packet = build_context_packet(
        "What should I eat?",
        [(make_chunk("c1", "Eat iron-rich foods."), 1.0)],
        safety_result={"risk_category": "SAFE_GENERAL", "message": None},
        user_context=UserContext(pregnancy_stage="second_trimester", region="Gujarat"),
    )
    text = packet.to_prompt_text()
    for section in ("USER CONTEXT", "USER QUESTION", "RETRIEVED SOURCES", "SAFETY RESULT", "EVIDENCE METADATA"):
        assert section in text
    assert "What should I eat?" in text
    assert "Eat iron-rich foods." in text
    assert "second_trimester" in text


def test_no_truncation_when_under_budget() -> None:
    packet = build_context_packet(
        "question",
        [(make_chunk("c1", "short content here"), 1.0)],
        safety_result={},
        max_tokens=1000,
    )
    assert not packet.truncated
    assert len(packet.retrieved_sources) == 1


def test_truncation_drops_lowest_ranked_chunks_when_over_budget() -> None:
    big_chunk_1 = make_chunk("c1", " ".join(["word"] * 50))
    big_chunk_2 = make_chunk("c2", " ".join(["word"] * 50))
    big_chunk_3 = make_chunk("c3", " ".join(["word"] * 50))
    packet = build_context_packet(
        "question",
        [(big_chunk_1, 3.0), (big_chunk_2, 2.0), (big_chunk_3, 1.0)],
        safety_result={},
        max_tokens=110,  # room for question + ~2 chunks, not all 3
    )
    assert packet.truncated
    included_ids = [s.chunk_id for s in packet.retrieved_sources]
    assert "c1" in included_ids
    assert "c2" in included_ids
    assert "c3" not in included_ids  # lowest-ranked, dropped first
    assert packet.total_tokens <= 110 or len(included_ids) <= 2


def test_at_least_one_chunk_always_included_even_if_over_budget_alone() -> None:
    huge_chunk = make_chunk("c1", " ".join(["word"] * 500))
    packet = build_context_packet(
        "question", [(huge_chunk, 1.0)], safety_result={}, max_tokens=10
    )
    assert len(packet.retrieved_sources) == 1
    assert not packet.truncated  # nothing was dropped, it's just over budget alone


def test_evidence_summary_counts_and_domains() -> None:
    packet = build_context_packet(
        "question",
        [
            (make_chunk("c1", "content one"), 1.0),
            (make_chunk("c2", "content two"), 0.9),
        ],
        safety_result={},
    )
    assert packet.evidence_summary.domains == ["NUTRITION"]
    assert packet.evidence_summary.evidence_level_counts == {"SUPPORTED": 2}


def test_needs_review_flagging_via_document_lookup() -> None:
    chunk = make_chunk("c1", "traditional content", document_id="doc-pending")
    packet = build_context_packet(
        "question",
        [(chunk, 1.0)],
        safety_result={},
        review_statuses={"doc-pending": "PENDING_CLINICAL_REVIEW"},
    )
    assert packet.evidence_summary.needs_review_chunk_ids == ["c1"]


def test_safety_result_is_carried_through_verbatim() -> None:
    safety_result = {"risk_category": "URGENT_ESCALATION", "message": "seek care"}
    packet = build_context_packet("question", [], safety_result=safety_result)
    assert packet.safety_result == safety_result
    assert "URGENT_ESCALATION" in packet.to_prompt_text()


def test_empty_retrieval_set_still_produces_valid_packet() -> None:
    packet = build_context_packet("question", [], safety_result={})
    assert packet.retrieved_sources == []
    assert "no sources retrieved" in packet.to_prompt_text()
