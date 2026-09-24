import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.evidence.ayurveda_provenance import (
    ProvenanceValidationError,
    check_evidence_label_justified,
    load_and_validate_documents,
)
from app.schemas.knowledge import (
    AyurvedicProvenance,
    Domain,
    EvidenceLevel,
    KnowledgeDocument,
)

SEED_PATH = Path(__file__).resolve().parents[2] / "knowledge" / "seed" / "seed.yaml"


def make_ayurveda_document(
    evidence_level: EvidenceLevel = EvidenceLevel.TRADITIONAL,
    modern_evidence_status: EvidenceLevel = EvidenceLevel.TRADITIONAL,
) -> KnowledgeDocument:
    return KnowledgeDocument(
        document_id="doc-1",
        title="t",
        content="c",
        domain=Domain.AYURVEDA,
        source_id="src-1",
        source_type="ayurvedic_classical_source",
        evidence_level=evidence_level,
        ayurvedic_provenance=AyurvedicProvenance(
            source="Charaka Samhita",
            book="Charaka Samhita",
            chapter="Sharirasthana 8",
            original_text="...",
            modern_evidence_status=modern_evidence_status,
        ),
    )


def test_load_and_validate_the_real_seed_file() -> None:
    """Regression test for the real gap found while building #15: the
    seed.yaml Ayurveda entries did not originally satisfy #1's schema."""
    raw = yaml.safe_load(SEED_PATH.read_text())
    documents = load_and_validate_documents(raw)
    assert len(documents) == len(raw)
    ayurveda_docs = [d for d in documents if d.domain == Domain.AYURVEDA]
    assert len(ayurveda_docs) == 2
    for doc in ayurveda_docs:
        assert doc.ayurvedic_provenance is not None
        assert doc.ayurvedic_provenance.source
        assert doc.ayurvedic_provenance.book


def test_load_and_validate_all_seed_entries_have_justified_evidence_labels() -> None:
    raw = yaml.safe_load(SEED_PATH.read_text())
    documents = load_and_validate_documents(raw)
    for doc in documents:
        result = check_evidence_label_justified(doc)
        assert result.justified, f"{doc.document_id}: {result.reason}"


def test_ayurveda_document_missing_provenance_raises_clear_error() -> None:
    raw = [
        {
            "document_id": "bad-doc",
            "title": "t",
            "content": "c",
            "domain": "AYURVEDA",
            "source_id": "src-1",
            "source_type": "ayurvedic_classical_source",
            "evidence_level": "TRADITIONAL",
        }
    ]
    with pytest.raises(ProvenanceValidationError, match="bad-doc"):
        load_and_validate_documents(raw)


def test_non_ayurveda_document_always_justified() -> None:
    doc = KnowledgeDocument(
        document_id="d1",
        title="t",
        content="c",
        domain=Domain.NUTRITION,
        source_id="s1",
        source_type="nutrition_reference",
        evidence_level=EvidenceLevel.SUPPORTED,
    )
    assert check_evidence_label_justified(doc).justified


def test_matching_evidence_level_and_provenance_status_is_justified() -> None:
    doc = make_ayurveda_document(
        evidence_level=EvidenceLevel.TRADITIONAL,
        modern_evidence_status=EvidenceLevel.TRADITIONAL,
    )
    assert check_evidence_label_justified(doc).justified


def test_mismatched_evidence_level_and_provenance_status_is_not_justified() -> None:
    """Section 11: don't let a document claim a label its own provenance
    record doesn't support."""
    doc = make_ayurveda_document(
        evidence_level=EvidenceLevel.SUPPORTED,
        modern_evidence_status=EvidenceLevel.TRADITIONAL,
    )
    result = check_evidence_label_justified(doc)
    assert not result.justified
    assert "does not match" in result.reason
