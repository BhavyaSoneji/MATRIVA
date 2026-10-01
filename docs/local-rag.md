# Offline RAG engine

MATRIVA answers questions with a retrieval-augmented pipeline that runs **entirely on your machine**: no Groq,
no Gemini, no embedding API, no web search. It is the default (`RAG_ENGINE=local`). The older Groq/Gemini
pipeline is still in the code behind `RAG_ENGINE=external`, but nothing calls it unless you opt in.

```
question
  │  safety pre-check (in the user's own language)           ← unchanged, runs first
  │  follow-up resolution ("what about ragi?" + previous turn)
  │  Hindi / Gujarati / Hinglish → English search query (hand glossary + the book's own bilingual terms)
  ▼
understand   intent (definition · quantity · safety · how-to · list · comparison) · classical authorities named
             · compound questions split when their halves are never discussed together
analyse      stemmed tokens · corpus synonyms · concepts found (with the words that named them) · related concepts
retrieve     seven signals, each its own ranking:
               BM25 (words)  │  character n-grams (OCR / spelling tolerant)  │  concept match
               latent semantic space (same meaning, different words)  │  structure (chapter & section titles)
               graph activation (personalised PageRank over the concept graph: multi-hop)
               pseudo-relevance feedback (vocabulary the best passages use)
fuse         weighted reciprocal rank fusion
rerank       coverage · term proximity · concept coverage · title match · semantic similarity · section match ·
             evidence strength · text quality · stage fit · diet fit · "asked about Ayurveda" and
             "asked about Caraka" preferences · a prior against scanned text on everyday questions
diversify    MMR + at most 3 passages per source, 2 per document
judge        idf-weighted sufficiency gate (best sentence · passages together · best passage; a concept counts as
             covered when the passage mentions it in other words) → answer or refuse
compose      pick real sentences (definitions for "what is", numbers for "how much", the named authority), drop
             near-duplicates, split modern vs traditional, number citations, add stage / allergy / diet notes
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

## Advanced signals

| signal | what it adds | code |
|---|---|---|
| Latent semantic space | passages about the same thing in different words; learned from the approved corpus with a truncated SVD (numpy, hashed features) | `semantic.py` |
| Structure | a passage inherits its section / chapter / document title, so a section is found even when its own OCR is unreadable | `index.structure_scores` |
| Graph activation | personalised PageRank over the concept graph reaches concepts the question did not name (multi-hop) | `graph.activation` |
| Pseudo-relevance feedback | terms frequent in the best passages but rare in the corpus are added to the search at low weight | `feedback.py` |
| Authority awareness | "what does Caraka say" prefers passages and sentences that cite him | `authorities.py` |
| Query understanding | intent, authorities, compound-question splitting | `understanding.py` |

Every signal sits behind `Config`, so each can be switched off.

## Evaluation

Four question sets in `evaluation/local_rag/`, because one set that you also tune on proves little:

* `questions.yaml` – the development set the engine was tuned on.
* `heldout.yaml`, `heldout2.yaml` – everyday paraphrases written after tuning; used to diagnose failures, so they
  guided some fixes (stemming of plurals, an over-broad "pregnant woman" concept, a prior against OCR text on
  everyday questions). They are development data now, not clean tests.
* `heldout3.yaml` – the clean test: written after all of that and never tuned on.

| set | in-scope | right doc first | in top 3 | MRR | answered | out-of-scope refused |
|---|---|---|---|---|---|---|
| tuned (`questions.yaml`) | 39 | 95% | 100% | 0.97 | 97% | 92% (12/13) |
| held-out 1 | 20 | 90% | 95% | 0.94 | 85% | 88% (7/8) |
| held-out 2 | 16 | 69% | 88% | 0.78 | 75% | 100% (6/6) |
| **held-out 3 (clean)** | 14 | **71%** | **86%** | **0.79** | **71%** | **83% (5/6)** |

So on questions it has never seen, the right document is first about 7 times in 10 and in the top three about 6 in 7.
That is the number to believe; the tuned set flatters it.

### Ablation (what each signal is worth)

`python evaluation/local_rag/ablation.py`, over the three development sets (75 in-scope, 27 out-of-scope questions):

| configuration | right doc first | top 3 | MRR | answered | refused |
|---|---|---|---|---|---|
| full pipeline | 88.0% | 96.0% | 0.923 | 89.3% | 92.6% |
| lexical only (BM25 + n-grams) | 85.3% | 96.0% | 0.905 | 90.6% | 92.6% |
| without semantic space | 84.0% | 96.0% | 0.903 | 88.0% | 92.6% |
| without structure | 86.7% | 96.0% | 0.917 | 89.3% | 92.6% |
| without graph activation | 86.7% | 96.0% | 0.917 | 89.3% | 92.6% |
| without feedback | 88.0% | 96.0% | 0.923 | 89.3% | 92.6% |
| without concepts | 85.3% | 96.0% | 0.910 | 88.0% | 92.6% |
| without n-grams | 85.3% | 96.0% | 0.904 | 86.6% | 96.3% |

Read this honestly: the lexical baseline is already strong, and the advanced signals add only a few points of
rank quality (the semantic space is worth the most, about 4 points of "right document first"). With 75 questions, one
question is 1.3 points, so differences under ~3 points are noise. Feedback, authority and compound-question handling
show no effect here because few of these questions exercise them; they are covered by unit tests instead
(`tests/test_local_rag_advanced.py`).

### Known failures

* An out-of-scope question can slip through when it shares a rare word with the book ("what is a good diet for my
  dog" matched a passage that mentions a dog). The sufficiency gate is lexical; it cannot know a dog is not a pregnancy topic.
* Paraphrases with no shared vocabulary and no matching concept still fail ("what should I do if my baby kicks less").
* `backend/tests/test_local_rag_eval.py` fails CI if the development sets regress.

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
