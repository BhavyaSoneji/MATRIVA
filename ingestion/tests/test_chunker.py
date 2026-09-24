import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.schemas.knowledge import Domain, EvidenceLevel, KnowledgeDocument  # noqa: E402

from pipelines.chunker import _is_heading, chunk_document  # noqa: E402


def make_document(content: str) -> KnowledgeDocument:
    return KnowledgeDocument(
        document_id="doc-1",
        title="Test Document",
        content=content,
        domain=Domain.NUTRITION,
        source_id="src-1",
        source_type="nutrition_reference",
        evidence_level=EvidenceLevel.SUPPORTED,
        topic="test_topic",
        pregnancy_stage="second_trimester",
        region="IN",
    )


def paragraph(word_count: int, prefix: str = "word") -> str:
    return " ".join(f"{prefix}{i}" for i in range(word_count)) + "."


def test_is_heading_detects_short_no_punctuation_line() -> None:
    assert _is_heading("Second Trimester Nutrition")
    assert not _is_heading("This is a full sentence with punctuation.")
    assert not _is_heading("line one\nline two")


def test_chunk_respects_target_size_range() -> None:
    # 5 paragraphs of 150 words each = 750 words total, should merge into
    # chunks within [300, 700] tokens rather than one giant or many tiny ones.
    content = "\n\n".join(paragraph(150, prefix=f"p{i}_w") for i in range(5))
    doc = make_document(content)
    chunks = chunk_document(doc)

    assert len(chunks) >= 1
    for chunk in chunks[:-1]:
        # only the last chunk may fall under the min (remainder content)
        assert 300 <= chunk.token_count <= 700
    assert chunks[-1].token_count <= 700


def test_chunk_never_splits_a_paragraph_across_chunks() -> None:
    paragraphs = [paragraph(100, prefix=f"p{i}_w") for i in range(6)]
    content = "\n\n".join(paragraphs)
    doc = make_document(content)
    chunks = chunk_document(doc)

    joined_chunk_content = "\n\n".join(c.content for c in chunks)
    for p in paragraphs:
        assert p in joined_chunk_content


def test_heading_stays_attached_to_following_content() -> None:
    content = "Second Trimester Nutrition\n\n" + paragraph(320)
    doc = make_document(content)
    chunks = chunk_document(doc)

    assert len(chunks) == 1
    assert chunks[0].content.startswith("Second Trimester Nutrition")


def test_oversized_paragraph_is_split_at_sentence_boundaries() -> None:
    sentences = " ".join(f"This is sentence number {i} of the paragraph." for i in range(200))
    doc = make_document(sentences)
    chunks = chunk_document(doc)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.token_count <= 700
        assert chunk.content.strip().endswith(".")


def test_chunk_metadata_completeness() -> None:
    content = "\n\n".join(paragraph(150) for _ in range(3))
    doc = make_document(content)
    chunks = chunk_document(doc)

    assert len(chunks) > 0
    for index, chunk in enumerate(chunks):
        assert chunk.chunk_id == f"doc-1-chunk-{index:04d}"
        assert chunk.document_id == doc.document_id
        assert chunk.source_id == doc.source_id
        assert chunk.domain == doc.domain
        assert chunk.topic == doc.topic
        assert chunk.pregnancy_stage == doc.pregnancy_stage
        assert chunk.evidence_level == doc.evidence_level
        assert chunk.region == doc.region
        assert chunk.language == doc.language
        assert chunk.token_count == len(chunk.content.split())


def test_chunk_index_is_sequential() -> None:
    content = "\n\n".join(paragraph(150) for _ in range(6))
    doc = make_document(content)
    chunks = chunk_document(doc)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
