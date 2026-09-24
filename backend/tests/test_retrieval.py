import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.retrieval import apply_metadata_filters, hybrid_retrieve  # noqa: E402
from app.rag.vector_store import InMemoryVectorStore  # noqa: E402
from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeChunk  # noqa: E402


def make_chunk(
    chunk_id: str,
    content: str = "generic content",
    domain: Domain = Domain.NUTRITION,
    pregnancy_stage: str | None = None,
    region: str | None = None,
) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id=f"doc-{chunk_id}",
        source_id="src-1",
        domain=domain,
        evidence_level=EvidenceLevel.SUPPORTED,
        content=content,
        chunk_index=0,
        pregnancy_stage=pregnancy_stage,
        region=region,
    )


# --- apply_metadata_filters ---------------------------------------------------

def test_filters_by_pregnancy_stage() -> None:
    chunks = [
        make_chunk("a", pregnancy_stage="second_trimester"),
        make_chunk("b", pregnancy_stage="third_trimester"),
    ]
    result = apply_metadata_filters(chunks, pregnancy_stage="second_trimester")
    assert [c.chunk_id for c in result] == ["a"]


def test_stage_agnostic_chunks_pass_any_stage_filter() -> None:
    chunks = [make_chunk("a", pregnancy_stage=None), make_chunk("b", pregnancy_stage="all")]
    result = apply_metadata_filters(chunks, pregnancy_stage="first_trimester")
    assert {c.chunk_id for c in result} == {"a", "b"}


def test_filters_by_domain() -> None:
    chunks = [make_chunk("a", domain=Domain.NUTRITION), make_chunk("b", domain=Domain.AYURVEDA)]
    result = apply_metadata_filters(chunks, domains=[Domain.AYURVEDA])
    assert [c.chunk_id for c in result] == ["b"]


def test_filters_by_region_but_allows_region_agnostic() -> None:
    chunks = [
        make_chunk("a", region="Gujarat"),
        make_chunk("b", region="Kerala"),
        make_chunk("c", region=None),
    ]
    result = apply_metadata_filters(chunks, region="Gujarat")
    assert {c.chunk_id for c in result} == {"a", "c"}


def test_no_filters_returns_everything() -> None:
    chunks = [make_chunk("a"), make_chunk("b")]
    assert apply_metadata_filters(chunks) == chunks


# --- hybrid_retrieve -----------------------------------------------------------

def test_hybrid_retrieve_requires_a_candidate_source() -> None:
    import pytest

    with pytest.raises(ValueError):
        hybrid_retrieve("query")


def test_hybrid_retrieve_keyword_only_path_ranks_by_overlap() -> None:
    chunks = [
        make_chunk("a", content="second trimester iron rich foods spinach moong dal"),
        make_chunk("b", content="unrelated content about car maintenance"),
    ]
    result = hybrid_retrieve("second trimester iron foods", candidate_chunks=chunks)
    assert result.chunks[0][0].chunk_id == "a"
    assert not result.used_fallback


def test_hybrid_retrieve_vector_path_uses_store() -> None:
    store = InMemoryVectorStore()
    near = make_chunk("near", content="closely related content")
    far = make_chunk("far", content="distant content")
    store.upsert_document("doc-near", [(near, [1.0, 0.0])])
    store.upsert_document("doc-far", [(far, [0.0, 1.0])])

    result = hybrid_retrieve(
        "query", query_embedding=[0.9, 0.1], vector_store=store, k=2
    )
    assert result.chunks[0][0].chunk_id == "near"


def test_hybrid_retrieve_applies_metadata_filters() -> None:
    chunks = [
        make_chunk("a", content="nutrition advice", domain=Domain.NUTRITION),
        make_chunk("b", content="nutrition advice", domain=Domain.AYURVEDA),
    ]
    result = hybrid_retrieve(
        "nutrition advice", candidate_chunks=chunks, domains=[Domain.AYURVEDA]
    )
    assert [c.chunk_id for c, _ in result.chunks] == ["b"]
    assert not result.used_fallback


def test_hybrid_retrieve_falls_back_when_filters_yield_nothing() -> None:
    chunks = [make_chunk("a", content="nutrition advice", domain=Domain.NUTRITION)]
    result = hybrid_retrieve(
        "nutrition advice", candidate_chunks=chunks, domains=[Domain.AYURVEDA]
    )
    # No AYURVEDA chunk exists, so metadata filtering alone would return
    # nothing -- must fall back to the unfiltered pool rather than returning
    # zero results outright.
    assert result.used_fallback
    assert len(result.chunks) == 1
    assert result.chunks[0][0].chunk_id == "a"


def test_hybrid_retrieve_respects_k() -> None:
    chunks = [make_chunk(str(i), content=f"content number {i} nutrition") for i in range(10)]
    result = hybrid_retrieve("nutrition", candidate_chunks=chunks, k=3)
    assert len(result.chunks) == 3
