"""Ayurveda evidence-labeling & provenance pipeline (issue #15, Section 11).

Two pieces:

1. `load_and_validate_documents`: an actual ingestion-path validation step.
   Before this issue, nothing in the codebase validated seed/ingested data
   against #1's `KnowledgeDocument` schema at load time -- `seed_qa.py`
   (#66) loads raw YAML dicts directly, bypassing validation entirely. This
   loads a list of raw document dicts, constructs `KnowledgeDocument` for
   each, and raises with a clear per-document error if any Ayurveda entry is
   missing required provenance (Section 11's `AyurvedicProvenance` is
   already enforced by #1's schema -- this is what actually calls that
   enforcement on real ingested data instead of leaving it theoretical).

2. `check_evidence_label_justified`: Section 11's "only use evidence labels
   that can actually be justified by the curated source" -- enforced here as
   a consistency check between `KnowledgeDocument.evidence_level` and
   `AyurvedicProvenance.modern_evidence_status`. These must agree; a
   document claiming `SUPPORTED` while its own provenance record says
   `TRADITIONAL` is drift, and drift is exactly how an unjustified label
   would sneak in unnoticed.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.knowledge import Domain, KnowledgeDocument


class ProvenanceValidationError(ValueError):
    """Raised when a document (typically dict input, pre-validation) fails
    to construct into a valid KnowledgeDocument, with the offending
    document_id included for traceability."""


def load_and_validate_documents(raw_documents: list[dict]) -> list[KnowledgeDocument]:
    """Construct and validate KnowledgeDocument for every raw entry (e.g.
    loaded from knowledge/seed/seed.yaml or a future ingestion source).
    Fails closed with a clear per-document error rather than silently
    admitting an incomplete Ayurveda entry into the corpus."""
    documents = []
    for raw in raw_documents:
        document_id = raw.get("document_id", "<unknown>")
        try:
            documents.append(KnowledgeDocument(**raw))
        except Exception as exc:
            raise ProvenanceValidationError(
                f"Document {document_id!r} failed validation: {exc}"
            ) from exc
    return documents


@dataclass
class EvidenceJustificationResult:
    justified: bool
    reason: str | None = None


def check_evidence_label_justified(document: KnowledgeDocument) -> EvidenceJustificationResult:
    """Section 11: 'Only use evidence labels that can actually be justified
    by the curated source/reviewer.' For AYURVEDA documents, that means
    `evidence_level` must agree with the document's own
    `ayurvedic_provenance.modern_evidence_status` -- a document can't claim
    a stronger (or different) evidence label than its own provenance record
    supports."""
    if document.domain != Domain.AYURVEDA:
        return EvidenceJustificationResult(justified=True)

    if document.ayurvedic_provenance is None:
        # Unreachable in practice (schema enforces this), but fail closed
        # rather than assume justified if it somehow happens.
        return EvidenceJustificationResult(
            justified=False, reason="AYURVEDA document has no ayurvedic_provenance"
        )

    if document.evidence_level != document.ayurvedic_provenance.modern_evidence_status:
        return EvidenceJustificationResult(
            justified=False,
            reason=(
                f"evidence_level={document.evidence_level} does not match "
                f"ayurvedic_provenance.modern_evidence_status="
                f"{document.ayurvedic_provenance.modern_evidence_status}"
            ),
        )

    return EvidenceJustificationResult(justified=True)
