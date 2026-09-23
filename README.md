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
├── frontend/            Next.js app (UI)
├── backend/
│   └── app/
│       ├── api/         route handlers
│       ├── models/      SQLAlchemy models
│       ├── schemas/     Pydantic schemas
│       ├── services/    business logic
│       ├── repositories/ data access
│       ├── rag/          retrieval, reranking, context construction
│       ├── safety/       pre-check, post-check, escalation
│       ├── recommendation/
│       ├── personalization/
│       ├── llm/          Groq client, prompts
│       └── evidence/     source/citation handling
├── knowledge/            curated source material (medical/ayurveda/nutrition/lifestyle/regional)
├── ingestion/            parsing, chunking, embeddings, metadata pipelines
├── evaluation/           retrieval/generation/safety eval datasets + reports
├── database/             migrations, seeds
├── docs/                 architecture, api, rag, safety, deployment docs
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
# backend
cd backend && pytest

# frontend e2e
cd frontend && npx playwright test
```

### Run evaluation

```bash
cd evaluation
python -m retrieval.run
python -m generation.run
python -m safety.run
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

- Prototype stage: knowledge base is seeded from a small curated set of sources, not comprehensive
  coverage of any domain.
- Clinical safety rules and thresholds must come from qualified medical reviewers — this codebase
  does not invent or certify clinical rules.
- Not a substitute for professional medical advice, diagnosis, or emergency care at any stage.

## Safety Considerations

- Safety classification is an independent module, never delegated solely to the LLM.
- If the safety subsystem fails, the system fails closed — it will not return an unrestricted
  medical recommendation.
- Traditional/Ayurvedic content is always labelled and never presented as having the same evidence
  status as modern medical guidance unless explicitly supported by a reviewed source.
- Retrieved document content is always treated as data, never as instructions (prompt-injection
  defense).
