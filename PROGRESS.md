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
