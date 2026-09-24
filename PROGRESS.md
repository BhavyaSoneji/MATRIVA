# Progress Log

Shared log for the team. **Add one entry every time you push a commit** (or finish a meaningful
chunk of work), newest entry at the top. Keep each entry short — a couple of lines is enough.

## How to add an entry

```
### YYYY-MM-DD — @your-github-handle
- What you did (1-3 bullets)
- Related issue(s): #<number>
- Status: in-progress / blocked / done
- Notes: anything the other two need to know (blockers, API changes, schema changes)
```

Paste your entry right below this line, above the older ones.

---

<!-- NEW ENTRIES GO HERE -->

### 2026-09-24 — @neevmodh
- #9: Added `backend/app/llm/groq_client.py` — `generate_from_packet(context_packet, ...)`, the
  full Groq integration: takes a #8 `ContextPacket`, enforces the Section 58 source-grounded
  system prompt, retries with exponential backoff on transient connection/timeout errors, fails
  immediately (no retry) on non-retryable API errors (auth/rate-limit/bad-request). Accepts an
  injectable `client` param for testability.
- Extracted `backend/app/llm/prompts.py` (`SOURCE_GROUNDED_SYSTEM_PROMPT`) out of `seed_qa.py`
  (#66) — same dedup pattern as #6's keyword_search.py extraction, re-verified `seed_qa.py`
  unaffected.
- 7 new tests (mocked Groq client, no live API needed): success path, system-prompt content/shape
  verified against Section 58's required phrases, retry-then-succeed on connection/timeout
  errors, retry exhaustion, and non-retryable errors failing fast without wasting a retry. 44/44
  passing across `backend/tests/`.
- Related issue(s): #9
- Status: partially verified — see notes
- Notes: **"tested against hallucination test cases" (acceptance criteria) is only partially
  satisfiable here** — I verified the system prompt is correctly constructed and sent, and the
  retry/error-handling logic, all via mocks; I did NOT verify actual model output against real
  hallucination test cases, since that needs a live Groq API key and #19's real evaluation
  dataset (not built yet). Whoever has a Groq key should run a handful of #19-style
  out-of-corpus questions through this once #19 exists. No personalization added, per spec
  ("Phase 4 = grounded QA only") — personalization is #11. Next: #10 (citation validation).

### 2026-09-24 — @neevmodh
- #8: Added `backend/app/rag/context_packet.py` — `build_context_packet(...)` assembles the 5
  required sections (Section 16): USER CONTEXT, USER QUESTION, RETRIEVED SOURCES, SAFETY RESULT,
  EVIDENCE METADATA, from #7's reranked output + #67's safety result. `ContextPacket.to_prompt_text()`
  renders it LLM-ready. Truncation drops lowest-ranked chunks first once a token budget
  (word-count approximation, default 2000) is exceeded, but always keeps at least one chunk even
  if it alone exceeds budget (avoids an empty-context edge case).
- 8 new tests: all 5 sections present, truncation behavior (drops lowest-ranked, respects order),
  evidence summary (domain/evidence-level counts, needs-review flagging), safety-result passthrough,
  empty-retrieval edge case. 37/37 passing across `backend/tests/`.
- Related issue(s): #8
- Status: done
- Notes: **same schema lesson as #7, caught before it shipped this time** — `KnowledgeChunk`
  doesn't carry `review_status` either (only `KnowledgeDocument` does), so `needs_review`
  flagging takes an explicit `review_statuses: dict[document_id, status]` lookup rather than
  reading a field the chunk schema never had. Next: #9 (Groq generation, full) — will need a live
  Groq key to fully verify, same caveat as #66's Sprint-0 script.

### 2026-09-24 — @neevmodh
- #7: Added `backend/app/rag/reranking.py` — `rerank(scored_chunks, context, source_types=...)`
  combines the incoming semantic/keyword `base_score` (from #6) with pregnancy-stage relevance,
  source quality, evidence level, regional relevance, and user-context term overlap, per Section
  12 Step 7.
- 7 new tests, explicitly covering ranking order changing across different user profiles (stage,
  region) per this issue's acceptance criteria, plus a fairness check: `TRADITIONAL` evidence
  scores within 0.05 of `SUPPORTED` when nothing else differs, so traditional/Ayurvedic content
  isn't structurally penalized (Section 11). 29/29 passing across `backend/tests/`.
- Related issue(s): #7
- Status: done
- Notes: **caught and fixed a schema bug while writing this** — `KnowledgeChunk` (#1) doesn't
  carry `source_type` (only the parent `KnowledgeDocument` does), so an initial `hasattr` check
  for it was silently always false, making the source-quality signal a dead no-op. Fixed by
  taking an explicit `source_types: dict[source_id, SourceType]` lookup instead of trying to read
  a field the chunk schema was never given. `source_quality`/`evidence_level` weights are
  documented as reflecting documentation rigor/claim-confidence, not domain legitimacy, in line
  with Section 11. Next: #8 (structured context packet construction).

### 2026-09-24 — @neevmodh
- #6: Added `backend/app/rag/retrieval.py` — `hybrid_retrieve(query, ...)` combines vector search
  (via #5's `VectorStore`), lenient metadata filtering (`apply_metadata_filters`: pregnancy_stage/
  domain/region per Section 13), and keyword-overlap scoring as a secondary signal, per Section 12
  Step 6. Metadata filtering is deliberately lenient (missing/"all"-tagged fields pass any filter)
  and **falls back to the unfiltered candidate pool if filters would otherwise return zero
  results**, per Section 13's "don't over-filter" guidance and this issue's acceptance criteria.
  Works with either a real `vector_store` + `query_embedding`, or `candidate_chunks` alone
  (keyword-only path, no embedding needed — same situation Sprint 0's `seed_qa.py` handles).
- Extracted `backend/app/rag/keyword_search.py` (`tokenize`, `keyword_overlap_score`) out of
  `seed_qa.py` so #6 doesn't duplicate Sprint 0's tokenizer; `seed_qa.py` now imports it. Reran
  `seed_qa.retrieve()` manually to confirm no behavior change.
- 11 new tests (`backend/tests/test_retrieval.py`); 22/22 passing across `backend/tests/`.
- Related issue(s): #6
- Status: done
- Notes: next is #7 (reranking — semantic relevance, stage, source quality, evidence level,
  region, user context), which sits directly downstream of this issue's output.

### 2026-09-24 — @neevmodh
- #5: Added `backend/app/rag/embeddings.py` (Gemini `embed_text`/`embed_chunk_contents`),
  `backend/app/models/knowledge.py` (`KnowledgeChunkRecord` ORM model with a pgvector `Vector(768)`
  column), and `backend/app/rag/vector_store.py` — a `VectorStore` protocol with two
  implementations: `InMemoryVectorStore` (pure-Python cosine similarity, fully unit-tested) and
  `PgVectorStore` (real Postgres+pgvector, same interface). Both implement re-indexing the same
  way: `upsert_document` replaces a document's entire chunk set, so old embeddings never remain
  active after a document changes (Section 15's requirement).
- 11 new tests (`backend/tests/test_vector_store.py`, `backend/tests/test_embeddings.py`), all
  passing — this is also the **first pytest-based test coverage for `backend/`** (Sprint 0's
  #66/#67 were only ad hoc script-verified, not pytest).
- Related issue(s): #5
- Status: partially verified — see notes
- Notes: **I don't have a live Postgres+pgvector instance or a Gemini API key in this
  environment**, so `PgVectorStore` and real embedding calls are untested here. What I *did*
  verify: the re-indexing/nearest-neighbor logic itself (via `InMemoryVectorStore`, same
  algorithm `PgVectorStore` expresses as SQL) and `embed_text`'s error handling + call shape
  (mocked, not a live API call). Acceptance criterion "basic retrieval query returns expected
  nearest neighbors on test data" is satisfied against `InMemoryVectorStore`; **whoever has
  `docker compose up db` running and a real `EMBEDDING_API_KEY` should run one live end-to-end
  check (embed → store → query) before this is considered fully closed.**
  Also flagging: `google-generativeai` (already pinned in `backend/requirements.txt` from Phase 0,
  not my choice) is now fully deprecated upstream — pip install prints "All support for the
  google.generativeai package has ended... switch to google.genai". Not blocking for the
  hackathon, but worth a migration issue before real production use.

### 2026-09-24 — @neevmodh
- #4: Added `ingestion/pipelines/quality.py` — `check_document_quality(document, corpus)` runs
  all 8 Section 38 checks (source exists, source identity, readability, metadata completeness,
  domain, evidence status, pregnancy relevance, safety relevance) plus Section 39 duplicate
  detection (exact hash + semantic similarity), returns a `QualityReport`. FAIL-severity checks
  block ingestion (`accepted=False`); WARN-severity checks (pregnancy/safety relevance) pass
  through but flag for human review.
- 27/27 tests passing across `ingestion/tests/` (11 new for quality.py).
- Related issue(s): #4
- Status: done
- Notes: semantic similarity uses `difflib.SequenceMatcher` over normalized text as a lightweight,
  dependency-free stand-in — swap for real embedding cosine similarity once #5 lands, same
  pattern as Sprint 0's `seed_qa.py` keyword overlap ahead of #6. Safety-relevance check reuses
  #67's `RED_FLAGS` list to flag undocumented danger-sign content. This closes out the ingestion
  pipeline's first four stages (#1-#4); #5 (embeddings + pgvector) is next but needs real infra
  (Postgres+pgvector running, a Gemini API key) I don't have in this environment — I'll write the
  code and note what can't be live-tested here.

### 2026-09-24 — @neevmodh
- #3: Added `ingestion/pipelines/chunker.py` — `chunk_document(document)` groups a
  `KnowledgeDocument`'s (#1) paragraph blocks into 300-700 token `KnowledgeChunk`s, never
  splitting a paragraph across chunks and always keeping a heading attached to the content that
  follows it. Oversized single paragraphs fall back to sentence-boundary splitting (never a blind
  character cut). Every chunk inherits the parent document's `source_id`/`domain`/`topic`/
  `pregnancy_stage`/`evidence_level`/`region`/`language` per Section 14.
- Added `ingestion/tests/test_chunker.py` — 7 unit tests (size-range compliance, no
  cross-chunk paragraph splitting, heading attachment, oversized-paragraph splitting, full
  metadata completeness, sequential chunk_index). All passing (16/16 across `ingestion/tests/`).
- Related issue(s): #3
- Status: done
- Notes: `chunker.py` bootstraps `backend/` onto `sys.path` to reuse #1's schema, since
  `ingestion/` and `backend/` are separate top-level dirs with no shared packaging/install step
  yet — flagging in case someone wants a cleaner shared-package approach later (e.g. #22 CI or a
  future refactor). Token counts are word-count approximations, not real LLM tokenization; swap
  `_count_tokens` for a real tokenizer if a later issue needs exact context-window fitting.
  Next: #4 (metadata enrichment + quality checks, incl. duplicate detection).

### 2026-09-24 — @neevmodh
- #2: Added `ingestion/pipelines/parser.py` — `extract_text_from_pdf` (PyMuPDF), `extract_text_from_docx`
  (python-docx), `extract_text` (dispatch by extension), `clean_text` (whitespace/hyphenation
  normalization without altering meaning), `parse_document` (parse+clean in one call). Implements
  the first stages of Section 37's pipeline (SOURCE FILE → PARSER → EXTRACTION → CLEANING).
- Added `ingestion/tests/test_parser.py` — 9 unit tests (PDF/docx extraction, unsupported-type
  rejection, 4 cleaning behaviors), generated sample fixtures on the fly (no binary test fixtures
  committed). All passing.
- Related issue(s): #2
- Status: done
- Notes: structural analysis + chunking is #3 (next), metadata enrichment + quality checks is #4.
  Run tests with `cd ingestion && python -m pytest tests/`.

### 2026-09-24 — @neevmodh
- #1: Defined the knowledge document/chunk schema in `backend/app/schemas/knowledge.py`
  (`KnowledgeDocument`, `KnowledgeChunk`, `AyurvedicProvenance`, `Domain`, `SourceType`,
  `EvidenceLevel`, `ReviewStatus`) per Master Prompt Sections 9/10/11/14; documented in
  `docs/rag.md`. Model enforces Section 11's rule in code, not just convention: an `AYURVEDA`
  document without `ayurvedic_provenance` raises a validation error.
- Related issue(s): #1
- Status: done
- Notes: **found and fixed a schema mismatch while formalizing this** — Section 11 is the only
  place the Master Prompt defines an evidence-label vocabulary (`TRADITIONAL`, `PRELIMINARY`,
  `LIMITED_EVIDENCE`, `MIXED_EVIDENCE`, `SUPPORTED`, `UNCERTAIN`, `NOT_ESTABLISHED`), and it's used
  generically across domains. `knowledge/seed/seed.yaml` (#65) had used a non-spec value
  (`ESTABLISHED`) for the FOGSI/IFCT entries — corrected to `SUPPORTED` in both `seed.yaml` and
  `backend/app/rag/seed_qa.py`'s `_evidence_label()`, retested, retrieval still works correctly.
  Sprint 1 ingestion (#2-#4) and the real ORM models should build against this schema directly.

### 2026-09-24 — @neevmodh
- Ran full OCR on `knowledge/ayurveda/Prasuti-Tantra-by-Dr-premvati-Tiwari.pdf` (408-page scanned
  book, no text layer) and committed the extract to `knowledge/ayurveda/Prasuti-Tantra-OCR.txt`
- Related issue(s): none directly (source material for future ingestion work, e.g. #2)
- Status: done
- Notes: installed Tesseract `hin`+`san` language data (via direct GitHub tessdata_fast download —
  Homebrew's bottle CDN was failing with connection resets), figured out the scan's rotation
  (each page renders sideways; needs -90deg), and OCR'd all 408 pages with `eng+hin`. English
  translation paragraphs (the book includes its own English translations of the Sanskrit) come out
  fairly clean; the Devanagari/Sanskrit verses have real recognition noise, as expected for a
  scanned classical text with no correction pass — **do not treat this file as authoritative**.
  It's raw material for someone to manually verify quotable verses/content against before they go
  into `knowledge/seed/seed.yaml` or the real ingestion pipeline (#2). Same Clinical Lead review
  requirement as the existing seed entries applies to anything pulled from this into product use.

### 2026-09-24 — @neevmodh
- #68: Drafted `docs/SUBMISSION.md` — Problem/Solution/Trustworthiness/Feasibility/Team structure
  per the approved roadmap, track/user/use-case fields filled per the official form, feasibility
  table mapping Sprint 0 (done pieces) → Sprint 1/2 (scoped backlog)
- #76: Tried to confirm the submission platform at healthathon.reskilll.com — it's a JS-rendered
  SPA, plain fetch returns only the page title with no route/form content, and the Chrome browser
  extension wasn't connected in this environment so I couldn't render it. **Still unconfirmed —
  needs a human to check the site directly (or reconnect the browser extension) and find the
  actual Round 1 submission form.**
- Related issue(s): #68, #76
- Status: in-progress (both blocked on human input)
- Notes: `docs/SUBMISSION.md` has 4 explicit `[TODO]` items that need a real person, not me:
  Clinical Lead's actual name/credentials, verified citations for the academic RAG-safety papers
  named in the brief (I won't fabricate bibliographic details), demo screenshots (waiting on
  Bhavya's #69 and Raj's #72-#74), and confirming #75 has actually closed before implying the
  Ayurveda content is signed off. #76 (submit) is blocked on #68 being finalized and on someone
  confirming the actual submission form.

### 2026-09-24 — @neevmodh
- #67: Added `backend/app/safety/pre_check.py` — thin keyword-based red-flag check
  (`precheck(query)`) against standard WHO/FOGSI obstetric danger signs (bleeding, severe
  headache/vision changes, reduced fetal movement, severe abdominal pain, convulsions, fluid
  leak, high fever, severe swelling, persistent vomiting). Matches route to `URGENT_ESCALATION`
  with a Section 22-compliant fallback (acknowledge + direct to professional/emergency care, no
  diagnosis, no false reassurance) instead of calling the LLM; everything else is `SAFE_GENERAL`.
- Related issue(s): #67
- Status: done (thin version only - full classifier is #12)
- Notes: verified 3 red-flag phrases correctly escalate and 1 normal question passes through.
  Red-flag list is the standard published WHO/FOGSI danger-sign set, not pulled from the actual
  FOGSI GCPR PDF (don't have it in-repo) — same caveat as #65: cross-check against the primary
  document and get Clinical Lead sign-off (#75) before this goes past the demo. Bhavya's `/chat`
  (#69) should call `precheck()` first and short-circuit on `URGENT_ESCALATION` before touching
  `seed_qa.answer_question()`.

### 2026-09-24 — @neevmodh
- #65: Added `knowledge/seed/seed.yaml` — 1 FOGSI/WHO ANC-schedule excerpt, 2 Garbhini Paricharya
  entries, 5 IFCT food entries, in the real schema shape (issue #1 fields)
- #66: Added `backend/app/rag/seed_qa.py` — `answer_question(query)` does keyword-overlap
  retrieval over the seed file + Groq call with the Section 58 source-grounded prompt, returns
  `{answer, sources[], evidence_label}`; callable by Bhavya's `/chat` (#69)
- Related issue(s): #65, #66
- Status: in-progress
- Notes: the Ayurveda source PDF (`knowledge/ayurveda/Prasuti-Tantra...pdf`) is a scanned image
  with no text layer, so I could not pull verbatim verses from it. The 2 Garbhini Paricharya
  entries use the standard Charaka Samhita Sharirasthana Ch.8 teaching (no invented citations)
  but are flagged `review_status: PENDING_CLINICAL_REVIEW` — **do not surface them in the demo
  or submission doc until #75 (Clinical Lead sign-off) closes.** IFCT nutrient values are
  approximate and flagged `PENDING_SOURCE_VERIFICATION` — verify against the actual IFCT 2017
  tables before using them in anything client-facing. `seed_qa.py` needs `LLM_API_KEY` (or
  `GROQ_API_KEY`) set to actually call Groq; retrieval-only path was tested without a key.

### 2026-09-23 — @neevmodh
- URGENT — Health-a-thon 2026 Round 1 is due **Sep 25** (not the full MVP, but written solution
  concept + methodology; real MVP is Nov 8 after shortlist). Track = Maternal & Women's Health,
  User = Patient/Caregiver, Use case = Patient Education & Digital Engagement.
- Opened milestone `R0: Round 1 Submission` and filed 12 issues (#65-#76, label `sprint-0`) split
  3 ways: seed knowledge + minimal RAG script + safety pre-check + submission doc (me), minimal
  /chat + ANC visit-schedule endpoints (Bhavya), minimal chat UI + visit card + demo polish (Raj)
- Full plan saved at the roadmap doc referenced in this conversation — single demo scenario: 2nd
  trimester patient asks a nutrition+Ayurveda question, gets a cited answer, sees her next ANC
  visit from the FOGSI 8-contact schedule
- Related issue(s): #65-#76
- Status: in-progress
- Notes: **Everyone drop other work and prioritize their R0 issues until Sep 25.** M1/M2/M3
  backlog resumes only if shortlisted (Oct 3). Clinical Lead (BAMS/MS-Gynaec) must sign off on the
  Garbhini Paricharya verses and ANC schedule before they go in the demo or write-up (#R0 checkpoint
  issue). Exact submission form/platform not yet confirmed — check healthathon.reskilll.com.

### 2026-09-23 — @neevmodh
- Moved the Ayurveda source PDF (`Prasuti-Tantra-by-Dr-premvati-Tiwari.pdf`) into `knowledge/ayurveda/`
- Audited docs/FEATURES.md against the 56 existing issues and filed 8 more to close gaps:
  #57 intent classification, #58 multi-domain response segmentation, #59 lifestyle engine (backend),
  #60 security hardening, #61 knowledge search & sources API, #62 feedback API,
  #63 conversation memory (session vs profile), #64 suggested questions & feedback UI
- Added a Feature → Issue coverage map to docs/FEATURES.md so every feature traces to an issue number
- Related issue(s): #57-#64
- Status: done
- Notes: total backlog is now 64 issues across M1/M2/M3, all feature areas from FEATURES.md have
  at least one tracking issue.

### 2025-09-23 — @neevmodh
- Created docs/FEATURES.md (full functionality list) and this PROGRESS.md
- Filed 56 GitHub issues across 3 milestones (M1/M2/M3), labeled and assigned per workstream
  (rag-ai/testing/review → @neevmodh, backend → @BhavyaSoneji, frontend → @Rajodedra)
- Added `.github/CODEOWNERS`
- Related issue(s): #21 (workflow setup)
- Status: done
- Notes: Backend uses Groq (generation) + Gemini (embeddings). Everyone: update this file after
  every commit so we always know real project status without digging through git log.
