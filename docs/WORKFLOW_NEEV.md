# RAG / AI / Testing / Review Workflow — Neev

Step-wise execution order for all `rag-ai`, `testing`, `review`, and `safety` issues
(assignee `@neevmodh`). Work top to bottom. Don't start a step until its "Depends on" column is
actually done — check [`PROGRESS.md`](../PROGRESS.md) for real status before jumping ahead.

## Sprint 0 — Health-a-thon Round 1 (due Sep 25)

Do these first, in this order. Nothing below this section matters until Round 0 ships.

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 1 | [#65](https://github.com/BhavyaSoneji/MATRIVA/issues/65) Hand-curate seed knowledge set | 1 FOGSI ANC-schedule excerpt, 1-2 Clinical-Lead-reviewed Garbhini Paricharya verses, 3-5 IFCT food entries, as a small JSON/YAML file under `knowledge/seed/` | — |
| 2 | [#66](https://github.com/BhavyaSoneji/MATRIVA/issues/66) Minimal retrieval + Groq generation script | Loads the seed file (in-memory embedding compare, no pgvector yet), calls Groq, returns `{answer, sources[], evidence_label}` for the demo question | Step 1 |
| 3 | [#67](https://github.com/BhavyaSoneji/MATRIVA/issues/67) Rule-based safety pre-check (thin) | Keyword list from FOGSI danger-signs sections; 3+ red-flag phrases correctly routed to a safe fallback | — |
| 4 | [#75](https://github.com/BhavyaSoneji/MATRIVA/issues/75) Clinical Lead review checkpoint | Get explicit sign-off on the ANC schedule + Garbhini Paricharya verses before they appear in the demo or write-up | Step 1 |
| 5 | [#68](https://github.com/BhavyaSoneji/MATRIVA/issues/68) Write & assemble Round 1 submission doc | Problem/Solution/Trustworthiness/Feasibility/Team sections, citing FOGSI/WHO/Charaka Samhita + academic RAG-safety literature, screenshots of the demo | Steps 2-4, Raj's #72-#74, Bhavya's #69-#71 |
| 6 | [#76](https://github.com/BhavyaSoneji/MATRIVA/issues/76) Confirm submission platform and submit | Locate the exact Round 1 form on healthathon.reskilll.com, submit before Sep 25 close | Step 5 |

### Step 2 detail — #66 minimal retrieval + generation script
1. Load the seed file from step 1 into memory.
2. Simple similarity match is enough (even keyword overlap if embeddings add friction) — full
   hybrid retrieval/reranking is Sprint 1 (#6, #7).
3. Call Groq with the source-grounded system prompt (Section 58: no invented facts, no fabricated
   citations, distinguish modern/traditional/uncertain evidence).
4. Expose as a plain callable function so Bhavya's `/chat` (#69) can import it directly — no
   service layer needed yet.

### Step 3 detail — #67 thin safety pre-check
1. Pull "danger signs" language directly from the FOGSI GCPR PDFs (bleeding, severe headache,
   reduced fetal movement, etc. — whatever the Clinical Lead confirms as appropriate for a demo).
2. Simple keyword match — no ML classifier yet (#12 is Sprint 1).
3. On match, short-circuit to a safe fallback message (acknowledge concern, direct to professional
   care) instead of calling the LLM.

**Coordination point:** Step 5 (submission doc) can't be finished until Raj and Bhavya's Sprint 0
issues produce a working demo to screenshot — write the doc's prose sections while waiting, then
drop in screenshots last.

---

## Sprint 1 — Foundation (if shortlisted, build sprint Oct 5 - Nov 8)

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 7 | [#21](https://github.com/BhavyaSoneji/MATRIVA/issues/21) CODEOWNERS + branch protection + PR review workflow | Enable branch protection on `main` requiring review + passing CI | — |
| 8 | [#22](https://github.com/BhavyaSoneji/MATRIVA/issues/22) CI pipeline | Lint/type-check/pytest for backend, lint/type-check/build for frontend, Playwright on PR | #7 |
| 9 | [#1](https://github.com/BhavyaSoneji/MATRIVA/issues/1) Knowledge document & chunk schema | Full schema (document_id, domain, evidence_level, etc. per Section 9 & 14) documented in `docs/rag.md` | Sprint 0 seed file (step 1) informs the real shape |

## Sprint 1 — Ingestion Pipeline

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 10 | [#2](https://github.com/BhavyaSoneji/MATRIVA/issues/2) Document parsing + cleaning | PyMuPDF/python-docx text extraction + normalization | #9 |
| 11 | [#3](https://github.com/BhavyaSoneji/MATRIVA/issues/3) Semantic chunking | 300-700 token chunks, structure-preserving, full metadata per chunk | #10 |
| 12 | [#4](https://github.com/BhavyaSoneji/MATRIVA/issues/4) Metadata enrichment + quality checks | Duplicate detection (hash + semantic similarity), reject-flow for failing docs | #11 |
| 13 | [#5](https://github.com/BhavyaSoneji/MATRIVA/issues/5) Gemini embeddings + pgvector storage | Real embedding pipeline replacing Sprint 0's in-memory compare; re-indexing invalidates old embeddings | #12, Bhavya's #24 |

## Sprint 1 — Retrieval & Generation

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 14 | [#6](https://github.com/BhavyaSoneji/MATRIVA/issues/6) Hybrid retrieval | Vector + metadata filter + keyword search, replacing Sprint 0's simple match | #13 |
| 15 | [#7](https://github.com/BhavyaSoneji/MATRIVA/issues/7) Reranking | Relevance + stage + evidence level + region + source quality | #14 |
| 16 | [#8](https://github.com/BhavyaSoneji/MATRIVA/issues/8) Structured context packet construction | Assemble user context + question + sources + safety result + evidence metadata for the LLM | #15 |
| 17 | [#9](https://github.com/BhavyaSoneji/MATRIVA/issues/9) Groq generation (full) | Replaces Sprint 0's minimal script; full source-grounded prompt against real retrieval | #16 |
| 18 | [#10](https://github.com/BhavyaSoneji/MATRIVA/issues/10) Citation validation | Every citation verified against actually-retrieved sources; fails closed on unverifiable citations | #17 |
| 19 | [#11](https://github.com/BhavyaSoneji/MATRIVA/issues/11) Personalized query rewriting | Query expansion using stage/diet/region/restrictions | #14, Bhavya's #28 |
| 20 | [#57](https://github.com/BhavyaSoneji/MATRIVA/issues/57) Chat intent classification | Classify into NUTRITION/EXERCISE/.../EMERGENCY/OTHER; safety overrides intent routing | #17 |
| 21 | [#58](https://github.com/BhavyaSoneji/MATRIVA/issues/58) Multi-domain query decomposition | Split responses into MODERN MEDICAL / TRADITIONAL-AYURVEDIC / EVIDENCE STATUS sections | #14, #17 |

## Sprint 1 — Safety (independent module)

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 22 | [#12](https://github.com/BhavyaSoneji/MATRIVA/issues/12) Safety pre-check classifier (full) | Replaces Sprint 0's thin keyword version; full SAFE_GENERAL/.../URGENT_ESCALATION routing | Step 4 checkpoint pattern continues — clinical rules reviewed by the Clinical Lead |
| 23 | [#13](https://github.com/BhavyaSoneji/MATRIVA/issues/13) Safety post-check validator | 5 independent checks: unsupported claims, dangerous recs, missing escalation, source consistency, evidence mismatch | #17 |
| 24 | [#14](https://github.com/BhavyaSoneji/MATRIVA/issues/14) Prompt injection defense | Retrieved text structurally isolated as data, never instructions; adversarial-document test | #16 |
| 25 | [#15](https://github.com/BhavyaSoneji/MATRIVA/issues/15) Ayurveda evidence-labeling & provenance pipeline | Full provenance (book/chapter/verse/translation) + evidence labels (TRADITIONAL/PRELIMINARY/etc.), all Clinical-Lead-reviewed | #12 (ingestion), Clinical Lead sign-off |

## Sprint 1 — Evaluation & Testing

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 26 | [#16](https://github.com/BhavyaSoneji/MATRIVA/issues/16) Retrieval evaluation harness | Recall@K, Precision@K, MRR against a >=20-query labeled dataset | #14 |
| 27 | [#17](https://github.com/BhavyaSoneji/MATRIVA/issues/17) Generation evaluation | Groundedness, citation correctness, completeness, clarity (automated + human-review checklist) | #18 |
| 28 | [#18](https://github.com/BhavyaSoneji/MATRIVA/issues/18) Safety evaluation test suite | >=15 test cases across all Section 19 categories, automated pass/fail vs expected routing | #22, #23 |
| 29 | [#19](https://github.com/BhavyaSoneji/MATRIVA/issues/19) Hallucination / grounding test suite | >=10 out-of-corpus questions, all must produce "insufficient evidence" | #17 |
| 30 | [#20](https://github.com/BhavyaSoneji/MATRIVA/issues/20) Full 12-case test suite (Section 52) | All 12 cases automated as integration tests against the full pipeline | #26-#29 complete |

Log progress in `PROGRESS.md` throughout both sprints, and use your `review` role to keep an eye
on Bhavya's and Raj's PRs as they land, per the CODEOWNERS routing set up in step 7.
