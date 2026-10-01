# Offline RAG engine

MATRIVA answers questions with a retrieval-augmented pipeline that runs **entirely on your machine**: no Groq,
no Gemini, no embedding API, no web search. It is the default (`RAG_ENGINE=local`). The older Groq/Gemini
pipeline is still in the code behind `RAG_ENGINE=external`, but nothing calls it unless you opt in.

```
question
  │  safety pre-check (in the user's own language)           ← unchanged, runs first
  │  follow-up resolution ("what about ragi?" + previous turn)
  │  Hindi / Gujarati / Hinglish → English search query (offline glossary)
  ▼
analyse      stemmed tokens · corpus synonyms · concepts found · related concepts (knowledge graph)
retrieve     BM25 (words) │ TF-IDF over character n-grams (OCR / spelling tolerant) │ concept match
fuse         reciprocal rank fusion
rerank       coverage · term proximity · concept coverage · title match · evidence strength ·
             text quality · stage fit · diet fit · "asked about Ayurveda" preference
diversify    MMR + at most 3 passages per source, 2 per document
judge        sufficiency gate: best-sentence, union and top-passage coverage (idf-weighted) → answer or refuse
compose      pick real sentences, drop near-duplicates, split modern vs traditional, number citations,
             add stage / allergy / diet notes
  ▼
answer (every sentence is quoted from an approved passage)  +  retrieval trace  +  follow-up suggestions
  │  safety post-check                                       ← unchanged
```

Code: `backend/app/rag/local/` (`text`, `index`, `graph`, `corpus`, `retriever`, `composer`, `engine`).

## Knowledge representation

* **Passages** – approved, active chunks only (the same review gate as everywhere else), each with its source,
  domain, evidence level, stage, region, locator (e.g. *scanned p. 181*) and text-quality score.
* **Knowledge graph** – 91 concepts (nutrients, foods, symptoms, conditions, practices, care, Ayurveda terms) in
  `backend/app/data/ontology.yaml`, with an is-a hierarchy (ragi → millet → grains). **Edges are not hand-written**:
  two concepts are linked when approved passages mention both, weighted by NPMI. Every link is traceable to text,
  and the map only shows what the reviewed sources say. See the **/map** card in the chat, or
  `GET /knowledge/graph?q=iron`.
* The index and graph rebuild automatically when documents are approved, rejected or reindexed.

## The book (Prasuti Tantra, Prof. Premvati Tiwari)

The scan is bilingual: Sanskrit/Hindi that OCR mangles, and English translation paragraphs that it reads well. The book
is represented at three levels, all derived deterministically from the OCR (no model, no network):

1. **Structure** (`ingestion/pipelines/book_structure.py`). The 11 chapters are found from their
   `अध्याय / CHAPTER / (TITLE)` headings in the body. Section rows come from the book's bilingual contents; because
   each scan is a two-page spread and the page numbers drift, every row is **verified by reading the body text near its
   predicted page**, and rows that cannot be found are dropped rather than guessed (93 verified of 109 parsed).
2. **Passages** (`ocr_english.py`). Only genuine English prose is kept (≈567 chunks, ≈94k words), cleaned and scored.
   Each chunk carries chapter, section, scanned page, readability, and the Hindi/Sanskrit original beside it as unverified
   provenance (shown under "Show the passage"; never searched or quoted).
3. **Knowledge representation** (`backend/app/data/book_index.json`, built by `backend/scripts/build_book_index.py`):
   chapters with titles in both languages, sections, main concepts (from the ontology), distinctive terms
   (TF-IDF across chapters — *dauhrda* surfaces for the pregnancy chapter), classical authorities cited per chapter
   (Vagbhata, Susruta, Caraka, Kasyapa …), and a Hindi ↔ English glossary from the contents. The glossary also lets
   Hindi questions be translated offline. Browse it in the chat with **/book**, or `GET /knowledge/book`.

Retrieval uses the structure: section and chapter titles are searched, so "monthwise dietary regimen" finds
*Ch. 5 › Monthwise dietary regimen, scanned p. 139*. Where that page's English OCR is too damaged to quote (two-column
pages sometimes merge), the answer says so and points at the page instead of quoting garbage.

Ingest one chapter per document (11 documents to review in *Admin → Documents*, all pending until approved):

```
python backend/scripts/ingest_real_knowledge.py --book-only --replace   # chapters
python backend/scripts/build_book_index.py                              # regenerate the representation
```

## Evaluation

`python evaluation/local_rag/run.py` builds the index from the repo's data files (guidelines, USDA foods, the
book) and asks `evaluation/local_rag/questions.yaml` (39 in-scope, 13 out-of-scope questions):

| metric | value |
|---|---|
| right document in top 1 / 3 / 5 | 95% / 100% / 100% |
| mean reciprocal rank | 0.97 |
| in-scope questions answered | 90% |
| out-of-scope questions refused | 92% (12 of 13) |

`backend/tests/test_local_rag_eval.py` fails CI if these drop. The one out-of-scope miss is "newborn vaccines",
which is genuinely near the pregnancy-vaccines passage. The thresholds in `retriever.py` were calibrated on this
question set, so treat the numbers as an upper bound for unseen questions.

## Sources behind the answers

Approved content in the default knowledge base: 20+ WHO / NHS / Government of India guidance entries (including six
from ICMR-NIN's *Dietary Guidelines for Indians*, the main source for Indian diet advice), 67 USDA nutrient profiles
for foods common in Indian diets, the FOGSI visit schedule, and the Prasuti Tantra English passages (11 chapters). Each is
paraphrased with its source URL; the wording has not been reviewed line by line by a clinician.

## Limits (honest)

* **Extractive, not generative.** It quotes; it cannot summarise across sources or reason. That is the price of
  never inventing a fact.
* **English knowledge base.** Hindi/Gujarati questions are translated by a small glossary, so unusual phrasings
  are missed. Answers are in English.
* **OCR noise.** Two-column pages sometimes merge into unreadable English. The structure still locates the right
  section and the answer points to the page, but cannot quote it. Hindi/Sanskrit text is kept only as provenance.
* Nothing is shown until it is approved: with nothing approved, the chat honestly says it has no evidence.
