# MATRIVA — Holistic AI Pregnancy Guidance Platform

A personalized, knowledge-grounded pregnancy guidance platform that integrates structured user
context with curated modern medical, Ayurvedic, nutritional, cultural, and lifestyle knowledge
through Retrieval-Augmented Generation, personalization, recommendation logic, source attribution,
and an independent safety layer.

**This is not a generic pregnancy chatbot.** It does not replace doctors, obstetricians, or
emergency care. It provides educational, source-grounded guidance and escalates high-risk queries
to professional medical care instead of answering them as ordinary wellness questions.

Full implementation spec: [`Master Prompt.txt`](./Master%20Prompt.txt)
Full feature list: [`docs/FEATURES.md`](./docs/FEATURES.md)
Live progress log: [`PROGRESS.md`](./PROGRESS.md)

---

## Status

The full M1 (Foundation + RAG Core) and M2 rag-ai backlog is implemented and tested: knowledge
schema, ingestion (parsing/chunking/quality checks), embeddings + pgvector storage, hybrid
retrieval, reranking, context packet construction, Groq generation, citation validation,
personalized query rewriting, intent classification, multi-domain segmentation, the full safety
classifier + post-check + prompt-injection defense, Ayurveda provenance validation, and retrieval/
generation/safety/hallucination evaluation harnesses — all wired together end-to-end in
[`backend/app/rag/pipeline.py`](./backend/app/rag/pipeline.py)'s `answer_query()`. 212 automated
tests pass across `backend/`, `ingestion/`, and `evaluation/`.

**What's not yet live-verified:** no live Groq or Gemini API key has been used against this code —
generation and embedding calls are tested against mocked/injected clients, not the real APIs.
pgvector storage/retrieval/re-indexing *has* been verified against a real Postgres instance.
Backend/frontend HTTP endpoints (`/chat`, auth, onboarding, etc.) are not yet built — `answer_query()`
is the callable the API layer should wrap.

**Known limitation, read before demoing:** keyword-overlap retrieval (the fallback in place until
live embeddings are wired in) cannot reliably distinguish an incidental word match from genuine
topical relevance — e.g. a question about a topic outside the corpus can still retrieve a
loosely-related chunk on nothing more than shared common vocabulary, and the pipeline will attempt
an answer instead of saying "insufficient evidence." See `PROGRESS.md`'s 2026-09-24 entry on
issue #19 for the full investigation; this needs real semantic embeddings (#5) to fix properly,
not a keyword threshold tweak (several were tried and don't work).

---

## Problem

Pregnant women navigating nutrition, lifestyle, and traditional practice questions get answers
from generic sources that blend modern medical evidence with unverified traditional claims,
without ever showing which is which, how strong the evidence is, or when to see a doctor instead.

## Solution

A pipeline that never lets the LLM be the sole source of truth:

```
USER PROFILE
      ↓
PREGNANCY CONTEXT
      ↓
QUERY UNDERSTANDING
      ↓
SAFETY PRE-CHECK
      ↓
KNOWLEDGE RETRIEVAL (RAG)
      ↓
PERSONALIZATION
      ↓
EVIDENCE FILTERING
      ↓
SAFETY POST-CHECK
      ↓
LLM RESPONSE GENERATION
      ↓
CITATIONS / SOURCES
      ↓
USER-FRIENDLY RESPONSE
```

Core principles: evidence first, retrieval before generation, safety before personalization,
personalization never overrides safety, and traditional/Ayurvedic knowledge is always explicitly
labelled and never silently equated with modern medical evidence.

---

## Architecture

```
                     ┌─────────────────────┐
                     │      Frontend       │
                     │     Next.js UI      │
                     └──────────┬──────────┘
                                │ HTTPS / REST
                                ▼
                     ┌─────────────────────┐
                     │      FastAPI        │
                     │       Backend       │
                     └──────────┬──────────┘
                                │
             ┌──────────────────┼──────────────────┐
             ▼                  ▼                  ▼
      ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
      │ PostgreSQL  │   │  RAG Engine  │   │ Safety Engine│
      │ + pgvector  │   │  Retrieval   │   │ Rules/Risk   │
      └─────────────┘   │  Reranking   │   │ Escalation   │
                         └──────┬───────┘   └──────────────┘
                                │
                                ▼
                         ┌──────────────┐
                         │   LLM (Groq) │
                         └──────┬───────┘
                                ▼
                        Answer + Sources
```

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js + TypeScript, Tailwind CSS, shadcn/ui |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy |
| Database | PostgreSQL |
| Vector search | pgvector |
| Cache / tasks | Redis |
| LLM (generation) | Groq |
| Embeddings | Gemini |
| Document processing | PyMuPDF, python-docx |
| Auth | JWT |
| Containers | Docker, Docker Compose |
| Testing | pytest, Playwright |

Deliberately not used at this stage: microservices, Kubernetes, fine-tuning/custom model training,
multiple vector databases, multiple orchestration frameworks. This is a modular monolith.

---

## Project Structure

```
matriva/
├── frontend/            Next.js app (UI) — Phase 0 scaffold, no feature pages yet
├── backend/
│   ├── app/
│   │   ├── api/          route handlers — not yet built
│   │   ├── models/       SQLAlchemy models (knowledge.py: pgvector-backed chunk table)
│   │   ├── schemas/      knowledge.py — KnowledgeDocument/Chunk/AyurvedicProvenance schema
│   │   ├── rag/          retrieval, reranking, context packets, embeddings, vector store,
│   │   │                 query rewriting, multi-domain segmentation, grounding guard,
│   │   │                 pipeline.py (answer_query — the full end-to-end orchestrator)
│   │   ├── safety/       classifier.py (full), post_check.py, prompt_injection.py,
│   │   │                 pre_check.py (thin Sprint-0 version, kept for existing callers)
│   │   ├── llm/          Groq client + prompts
│   │   ├── evidence/     citation validation, Ayurveda provenance validation
│   │   ├── recommendation/, personalization/  not yet built
│   │   └── core/         config, db
│   ├── tests/            pytest — 149 tests
│   └── scripts/          verify_pgvector_live.py — manual real-Postgres check
├── knowledge/
│   ├── seed/seed.yaml    curated seed knowledge set (demo corpus)
│   └── ayurveda/         source PDF + OCR text extract
├── ingestion/            pipelines/ (parser, chunker, quality checks) + tests — 27 tests
├── evaluation/           retrieval/generation/safety/hallucination eval harnesses + datasets
│                         + reports/ + tests/ — 36 tests
├── database/             migrations, seeds
├── docs/                 architecture, api, rag, safety, deployment, SUBMISSION.md
└── docker-compose.yml
```

---

## Getting Started

### Prerequisites
- Docker + Docker Compose
- Node.js 20+
- Python 3.11+
- A Groq API key and a Gemini API key

### Environment variables
Copy `.env.example` to `.env` and fill in:

```
DATABASE_URL=
REDIS_URL=
VECTOR_DATABASE_URL=

LLM_PROVIDER=groq
LLM_API_KEY=
LLM_MODEL=

EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=

JWT_SECRET=
```

Never commit real secrets. `.env` is gitignored.

### Run the stack

```bash
# 1. Start Postgres (with pgvector) + Redis
docker compose up -d db redis

# 2. Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# 3. Frontend
cd frontend
npm install
npm run dev
```

### Run knowledge ingestion

```bash
cd ingestion
python -m pipelines.run --source ../knowledge/ayurveda
```

### Run tests

```bash
# backend (149 tests) + lint/type-check
cd backend && ruff check . && mypy app/ && pytest

# ingestion (27 tests)
cd ingestion && pytest tests/

# evaluation harnesses (36 tests)
cd evaluation && pytest tests/

# frontend lint/typecheck/build + e2e
cd frontend && npm run lint && npm run typecheck && npm run build
cd frontend && npx playwright install --with-deps chromium && npm run test:e2e
```

### Run evaluation harnesses

Each writes a JSON report to `evaluation/reports/`. `generation.run` and any live-pipeline check
need `LLM_API_KEY`/`GROQ_API_KEY`; without one they run in a self-test mode against curated
example responses instead of live model output.

```bash
cd evaluation
python -m retrieval.run       # Recall@K, Precision@K, MRR, nDCG@K against knowledge/seed/seed.yaml
python -m generation.run      # groundedness, citation correctness, relevance, completeness
python -m safety.run          # safety classifier routing correctness (21 test cases)
python -m hallucination.run   # out-of-corpus questions -> must return "insufficient evidence"
```

### Verify pgvector against a real Postgres instance

The automated test suite only exercises an in-memory vector store double. To check the real
pgvector-backed implementation:

```bash
docker compose up -d db
cd backend
export DATABASE_URL=postgresql+psycopg://matriva:matriva@localhost:5432/matriva
python scripts/verify_pgvector_live.py
```

---

## Team & Workflow

| Workstream | Owner | Scope |
|---|---|---|
| RAG / AI / Safety / Testing / Code Review | [@neevmodh](https://github.com/neevmodh) | `backend/app/rag`, `backend/app/safety`, `backend/app/llm`, `backend/app/evidence`, `ingestion/`, `evaluation/` |
| Backend | [@BhavyaSoneji](https://github.com/BhavyaSoneji) | `backend/`, `database/`, API endpoints, DB models |
| Frontend | [@Rajodedra](https://github.com/Rajodedra) | `frontend/`, all UI pages |

- Full backlog is tracked as GitHub Issues across 3 milestones (`M1: Foundation + RAG Core`,
  `M2: Personalization + Safety + Domain Engines`, `M3: Frontend + Admin + Evaluation + Deploy`).
- Every feature in [`docs/FEATURES.md`](./docs/FEATURES.md) maps to a tracked issue.
- Ownership/review routing is enforced via [`.github/CODEOWNERS`](./.github/CODEOWNERS).
- **After every commit, add a short entry to [`PROGRESS.md`](./PROGRESS.md)** so the team always
  knows real project status without digging through git log.

---

## Limitations

- Prototype stage: knowledge base is seeded from a small curated set of sources (8 documents in
  `knowledge/seed/seed.yaml`), not comprehensive coverage of any domain.
- Clinical safety rules and thresholds must come from qualified medical reviewers — this codebase
  does not invent or certify clinical rules. Ayurvedic content is explicitly marked
  `PENDING_CLINICAL_REVIEW` until a Clinical Lead signs off.
- **Retrieval is keyword-overlap-based, not semantic**, until real embeddings (Gemini, via
  `backend/app/rag/embeddings.py`) are exercised against a live API key. This has a real,
  measured consequence: the hallucination/grounding test suite
  (`evaluation/hallucination/`) currently only reliably catches out-of-corpus questions that
  share literally zero vocabulary with the seed corpus — a question on a related-but-uncovered
  topic can still retrieve a loosely-matching chunk and get an attempted answer instead of an
  "insufficient evidence" response. See `PROGRESS.md` (2026-09-24, issue #19) for the investigation.
- Generation (Groq) and embedding (Gemini) API calls are tested against injected fake clients, not
  verified against the live APIs, in this codebase's current state.
- Not a substitute for professional medical advice, diagnosis, or emergency care at any stage.

## Safety Considerations

- Safety classification is an independent module, never delegated solely to the LLM.
- If the safety subsystem fails, the system fails closed — it will not return an unrestricted
  medical recommendation.
- Traditional/Ayurvedic content is always labelled and never presented as having the same evidence
  status as modern medical guidance unless explicitly supported by a reviewed source.
- Retrieved document content is always treated as data, never as instructions (prompt-injection
  defense).
