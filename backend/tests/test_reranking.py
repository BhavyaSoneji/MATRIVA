import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.reranking import UserContext, rerank  # noqa: E402
from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeChunk, SourceType  # noqa: E402


def make_chunk(
    chunk_id: str,
    content: str = "generic content",
    pregnancy_stage: str | None = None,
    region: str | None = None,
    evidence_level: EvidenceLevel = EvidenceLevel.SUPPORTED,
    source_id: str = "src-1",
) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        source_id=source_id,
        domain=Domain.NUTRITION,
        evidence_level=evidence_level,
        content=content,
        chunk_index=0,
        pregnancy_stage=pregnancy_stage,
        region=region,
    )


def test_stage_match_reorders_equal_base_score_chunks() -> None:
    a = make_chunk("a", pregnancy_stage="first_trimester")
    b = make_chunk("b", pregnancy_stage="third_trimester")
    scored = [(a, 1.0), (b, 1.0)]

    result_first = rerank(scored, UserContext(pregnancy_stage="first_trimester"))
    assert result_first[0][0].chunk_id == "a"

    result_third = rerank(scored, UserContext(pregnancy_stage="third_trimester"))
    assert result_third[0][0].chunk_id == "b"


def test_region_match_reorders_equal_base_score_chunks() -> None:
    a = make_chunk("a", region="Gujarat")
    b = make_chunk("b", region="Kerala")
    scored = [(a, 1.0), (b, 1.0)]

    result_gujarat = rerank(scored, UserContext(region="Gujarat"))
    assert result_gujarat[0][0].chunk_id == "a"

    result_kerala = rerank(scored, UserContext(region="Kerala"))
    assert result_kerala[0][0].chunk_id == "b"


def test_no_context_leaves_order_by_base_score() -> None:
    a = make_chunk("a")
    b = make_chunk("b")
    result = rerank([(a, 0.5), (b, 0.9)])
    assert result[0][0].chunk_id == "b"


def test_source_quality_breaks_ties() -> None:
    a = make_chunk("a", source_id="guideline-src")
    b = make_chunk("b", source_id="traditional-src")
    scored = [(a, 1.0), (b, 1.0)]

    result = rerank(
        scored,
        source_types={
            "guideline-src": SourceType.MEDICAL_GUIDELINE,
            "traditional-src": SourceType.TRADITIONAL_REFERENCE,
        },
    )
    assert result[0][0].chunk_id == "a"


def test_evidence_level_affects_ranking_among_equal_base_scores() -> None:
    supported = make_chunk("supported", evidence_level=EvidenceLevel.SUPPORTED)
    uncertain = make_chunk("uncertain", evidence_level=EvidenceLevel.UNCERTAIN)
    result = rerank([(supported, 1.0), (uncertain, 1.0)])
    assert result[0][0].chunk_id == "supported"


def test_traditional_evidence_not_penalized_relative_to_supported() -> None:
    """Section 11: traditional knowledge must not be treated as inherently
    lower-value than modern medical content."""
    supported = make_chunk("supported", evidence_level=EvidenceLevel.SUPPORTED)
    traditional = make_chunk("traditional", evidence_level=EvidenceLevel.TRADITIONAL)
    result = rerank([(supported, 1.0), (traditional, 1.0)])
    scores = {chunk.chunk_id: score for chunk, score in result}
    assert abs(scores["supported"] - scores["traditional"]) < 0.05


def test_context_terms_boost_matching_content() -> None:
    matching = make_chunk("matching", content="vegetarian diet options for pregnant women")
    nonmatching = make_chunk("nonmatching", content="general pregnancy wellbeing information")
    result = rerank(
        [(matching, 1.0), (nonmatching, 1.0)],
        UserContext(context_terms=["vegetarian", "diet"]),
    )
    assert result[0][0].chunk_id == "matching"
