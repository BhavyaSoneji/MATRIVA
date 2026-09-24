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
[`backend/app/rag/pipeline.py`](./backend/app/rag/pipeline.py)'s `answer_query()`. 233 automated
tests pass across `backend/`, `ingestion/`, and `evaluation/`.

**What's not yet live-verified:** no live Groq or Gemini API key has been used against this code —
generation and embedding calls are tested against mocked/injected clients, not the real APIs.
pgvector storage/retrieval/re-indexing has been verified against a real Postgres instance.
The backend HTTP layer is now implemented and wraps the canonical RAG pipeline; the local Docker
stack (PostgreSQL/pgvector, Redis, FastAPI, and Next.js) has also been smoke-tested. Demo seed
records are synthetic and must not be treated as current clinical guidance.

**Known limitation, read before demoing:** the no-key local fallback uses keyword retrieval and
cannot reliably distinguish an incidental word match from genuine topical relevance. The full
semantic path is implemented on the RAG branch, but live provider calls still require valid API
keys and a reviewed source corpus.

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
├── frontend/            Next.js app (UI) — production build scaffold
├── backend/
│   ├── app/
│   │   ├── api/          FastAPI routers for auth, profile, chat, knowledge, admin, evaluation
│   │   ├── models/       SQLAlchemy application models and evidence/guideline metadata
│   │   ├── schemas/      API schemas + canonical RAG knowledge schemas
│   │   ├── rag/          full RAG pipeline + SQLAlchemy/API adapter
│   │   ├── safety/       full classifier/post-check/prompt-injection defense + API rules adapter
│   │   ├── services/     auth, profile, chat, recommendations, admin, privacy, evaluation
│   │   └── core/         config, database, security, rate limiting, observability
│   ├── tests/            backend unit/integration and RAG regression tests
│   └── scripts/          pgvector verification and secret scan
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
Copy `.env.example` to `.env` and set a unique `JWT_SECRET` (at least 32 characters).
Never commit real secrets; `.env` is gitignored. `DEMO_MODE` must be `false` in production.

```bash
cp .env.example .env
```

### Run the stack

```bash
# Full local stack (Postgres/pgvector + Redis + API + frontend)
docker compose up --build

# Or run the backend directly
cd backend
python -m pip install -r requirements-dev.txt
alembic upgrade head
python ../database/seed/seed.py  # optional synthetic demo data
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`; OpenAPI is at `http://localhost:8000/docs`.
The production-oriented compose file is `docker-compose.prod.yml`; see
[`docs/deployment.md`](./docs/deployment.md) before deploying.

### Run knowledge ingestion

```bash
cd ingestion
python -m pipelines.run --source ../knowledge/ayurveda
```

### Run tests

```bash
# backend API + RAG tests, lint, type-check, and secret scan
cd backend
python -m pytest -q
ruff check .
python scripts/secret_scan.py --root ..

# ingestion
cd ../ingestion && pytest tests/

# evaluation harnesses
cd ../evaluation && pytest tests/

# frontend lint/typecheck/build + e2e
cd ../frontend && npm run lint && npm run typecheck && npm run build
npx playwright install --with-deps chromium && npm run test:e2e
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
