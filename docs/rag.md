# RAG Pipeline

Status: knowledge document/chunk schema defined (#1). Ingestion (#2-#4), embeddings/retrieval
(#5-#8), and generation (#9-#10) are Sprint 1 work, not yet implemented — Sprint 0's `/backend/app/rag/seed_qa.py`
is a scoped-down stand-in (in-memory keyword retrieval, no pgvector) for the Round 1 demo only.

## Knowledge document & chunk schema (#1)

Pydantic models: [`backend/app/schemas/knowledge.py`](../backend/app/schemas/knowledge.py).
Defined per Master Prompt Section 9 (Knowledge Document Model), Section 10 (Knowledge Domains),
Section 11 (Ayurveda Data Rule), and Section 14 (Chunking Strategy). Maps to the `knowledge_documents`,
`knowledge_chunks`, and `ayurvedic_sources` tables from Section 8 once the ORM models land.

### `KnowledgeDocument`

| Field | Type | Notes |
|---|---|---|
| `document_id` | str | |
| `title` | str | |
| `content` | str | |
| `domain` | `Domain` enum | `MODERN_MEDICAL`, `AYURVEDA`, `NUTRITION`, `LIFESTYLE`, `REGIONAL_CULTURAL` (Section 10) |
| `subdomain` | str? | e.g. `antenatal_care`, `garbhini_paricharya` |
| `source_id` | str | |
| `source_type` | `SourceType` enum | `medical_guideline`, `clinical_reference`, `textbook`, `ayurvedic_classical_source`, `traditional_reference`, `nutrition_reference`, `institutional_guidance` (Section 9). Do not invent sources outside these types. |
| `publication_date` | str? | |
| `version` | str | default `"1.0"` |
| `language` | str | default `"en"` |
| `region` | str? | |
| `pregnancy_stage` | str? | |
| `topic` | str? | |
| `evidence_level` | `EvidenceLevel` enum | see below |
| `review_status` | `ReviewStatus` enum | default `UNVERIFIED` |
| `reviewed_by` | str? | |
| `reviewed_at` | datetime? | |
| `safety_tags` | list[str] | |
| `ayurvedic_provenance` | `AyurvedicProvenance`? | **required when `domain == AYURVEDA`** — enforced by the model, not just convention |

### `KnowledgeChunk`

| Field | Type | Notes |
|---|---|---|
| `chunk_id` | str | |
| `document_id` | str | |
| `source_id` | str | |
| `domain` | `Domain` enum | |
| `topic` | str? | |
| `pregnancy_stage` | str? | |
| `evidence_level` | `EvidenceLevel` enum | |
| `region` | str? | |
| `language` | str | default `"en"` |
| `content` | str | chunk text (not in Section 14's metadata list, but obviously required) |
| `chunk_index` | int | position within parent document |
| `token_count` | int? | |

Target 300-700 tokens per chunk, structure-preserving (heading/section/source/page/paragraph
relationship) — the actual chunking algorithm is #3.

### `AyurvedicProvenance` (Section 11: AYURVEDA DATA RULE)

Traditional knowledge must **never** be silently converted into a modern medical claim. Every
Ayurvedic source retains:

`source`, `book`, `chapter`, `verse_or_page`, `original_text`, `translation`, `interpretation`,
`traditional_context`, `modern_evidence_status` (an `EvidenceLevel`, set explicitly and
independently of the traditional content itself).

### `EvidenceLevel`

The **only** evidence-label vocabulary the Master Prompt defines (Section 11), and it's used
generically across all domains — Section 9 and Section 14 both reference an `evidence_level`
field with no domain-specific enum of their own:

`TRADITIONAL`, `PRELIMINARY`, `LIMITED_EVIDENCE`, `MIXED_EVIDENCE`, `SUPPORTED`, `UNCERTAIN`,
`NOT_ESTABLISHED`.

Only use a label that can actually be justified by the curated source/reviewer — don't default to
`SUPPORTED` just because a source looks authoritative.

> **Note:** `knowledge/seed/seed.yaml` (#65, Sprint 0) originally used a non-spec value
> (`ESTABLISHED`) for modern-medical/nutrition entries before this schema was formalized. It's
> been corrected to `SUPPORTED` to match this vocabulary.

### `ReviewStatus`

Not explicitly enumerated in the Master Prompt beyond "if a source has not been verified, mark it
`UNVERIFIED`" (Section 9). `UNVERIFIED` is that generic state; `PENDING_SOURCE_VERIFICATION` and
`PENDING_CLINICAL_REVIEW` are this project's refinement so tooling can distinguish *why* something
isn't cleared (a numeric/factual claim needing a source check, vs. traditional/clinical content
needing the Clinical Lead's sign-off — see [#75](https://github.com/BhavyaSoneji/MATRIVA/issues/75)).

`UNVERIFIED`, `PENDING_SOURCE_VERIFICATION`, `PENDING_CLINICAL_REVIEW`, `REVIEWED_APPROVED`,
`REJECTED`.

## Retrieval metadata filtering (Section 13, forward reference for #6)

Retrieval must not rely solely on embeddings — combine with metadata filters, e.g.
`pregnancy_stage = second_trimester AND domain IN (MODERN_MEDICAL, NUTRITION, AYURVEDA) AND
region = Gujarat` when region-specific info is relevant. Don't over-filter in a way that removes
important general medical information. Implemented in #6 (Sprint 1); Sprint 0's `seed_qa.py` uses
plain keyword overlap only.

## Backend/API integration

The API now uses a small SQLAlchemy-to-RAG adapter. It converts approved ORM chunks into the
canonical Pydantic chunks, calls the full `answer_query()` pipeline when a provider key is
configured, and otherwise uses a deterministic source-grounded local fallback for development.
The HTTP contract is `app.rag.pipeline.answer_question()`.

Only active, approved documents from approved sources are eligible. Guideline registry entries
that are retired or past their review due date are excluded. The demo seed is synthetic and must
not be presented as a complete or current clinical corpus.
