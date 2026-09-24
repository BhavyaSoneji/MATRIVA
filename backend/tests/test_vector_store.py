import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.vector_store import InMemoryVectorStore, cosine_similarity
from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeChunk


def make_chunk(chunk_id: str, document_id: str, domain: Domain = Domain.NUTRITION) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        source_id="src-1",
        domain=domain,
        evidence_level=EvidenceLevel.SUPPORTED,
        content=f"content for {chunk_id}",
        chunk_index=0,
    )


def test_cosine_similarity_identical_vectors_is_one() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_similarity_orthogonal_vectors_is_zero() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_opposite_vectors_is_negative_one() -> None:
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0


def test_query_returns_nearest_neighbor_first() -> None:
    store = InMemoryVectorStore()
    near = make_chunk("c1", "doc-1")
    far = make_chunk("c2", "doc-2")
    store.upsert_document("doc-1", [(near, [1.0, 0.0, 0.0])])
    store.upsert_document("doc-2", [(far, [0.0, 1.0, 0.0])])

    results = store.query([0.9, 0.1, 0.0], k=2)

    assert [chunk.chunk_id for chunk, _ in results] == ["c1", "c2"]
    assert results[0][1] > results[1][1]


def test_query_respects_k() -> None:
    store = InMemoryVectorStore()
    for i in range(10):
        store.upsert_document(f"doc-{i}", [(make_chunk(f"c{i}", f"doc-{i}"), [float(i), 0.0])])

    results = store.query([5.0, 0.0], k=3)
    assert len(results) == 3


def test_query_filters_by_domain() -> None:
    store = InMemoryVectorStore()
    nutrition_chunk = make_chunk("c1", "doc-1", domain=Domain.NUTRITION)
    ayurveda_chunk = make_chunk("c2", "doc-2", domain=Domain.AYURVEDA)
    store.upsert_document("doc-1", [(nutrition_chunk, [1.0, 0.0])])
    store.upsert_document("doc-2", [(ayurveda_chunk, [1.0, 0.0])])

    results = store.query([1.0, 0.0], k=5, domain=Domain.AYURVEDA)

    assert len(results) == 1
    assert results[0][0].chunk_id == "c2"


def test_reindex_replaces_old_chunks_entirely() -> None:
    """Section 15: when a document changes, old embeddings must not silently
    remain active."""
    store = InMemoryVectorStore()
    old_chunk = make_chunk("old-chunk", "doc-1")
    store.upsert_document("doc-1", [(old_chunk, [1.0, 0.0])])
    assert store.chunk_count == 1

    new_chunk_a = make_chunk("new-chunk-a", "doc-1")
    new_chunk_b = make_chunk("new-chunk-b", "doc-1")
    store.upsert_document(
        "doc-1", [(new_chunk_a, [0.0, 1.0]), (new_chunk_b, [0.0, 1.0])]
    )

    assert store.chunk_count == 2
    all_ids = {chunk.chunk_id for chunk, _ in store.query([0.0, 1.0], k=10)}
    assert "old-chunk" not in all_ids
    assert all_ids == {"new-chunk-a", "new-chunk-b"}


def test_reindex_does_not_affect_other_documents() -> None:
    store = InMemoryVectorStore()
    other_doc_chunk = make_chunk("other", "doc-2")
    store.upsert_document("doc-2", [(other_doc_chunk, [1.0, 0.0])])

    store.upsert_document("doc-1", [(make_chunk("c1", "doc-1"), [0.0, 1.0])])
    store.upsert_document("doc-1", [(make_chunk("c1-v2", "doc-1"), [0.0, 1.0])])

    all_ids = {chunk.chunk_id for chunk, _ in store.query([1.0, 1.0], k=10)}
    assert all_ids == {"other", "c1-v2"}
