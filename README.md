# MATRIVA — Holistic AI Pregnancy Guidance Platform

**A personalized, evidence-grounded pregnancy companion** that combines a woman's own profile with
curated modern medical, Ayurvedic, nutritional, cultural, and lifestyle knowledge — through
retrieval-augmented generation, an independent safety layer, and transparent source attribution.

> **This is not a generic pregnancy chatbot.** It does not replace doctors, obstetricians, or
> emergency care. It answers from a reviewed knowledge base, always shows where an answer comes
> from and how strong the evidence is, and escalates high-risk queries to professional care
> instead of answering them as ordinary wellness questions.

📄 Full implementation spec — [`Master Prompt.txt`](./Master%20Prompt.txt)
📋 Full feature list — [`docs/FEATURES.md`](./docs/FEATURES.md)
⚖️ Policy & compliance alignment — [`docs/COMPLIANCE.md`](./docs/COMPLIANCE.md)
🗓️ Live progress log — [`PROGRESS.md`](./PROGRESS.md)

---

## Status

**Backend, RAG pipeline, and frontend are all implemented and wired end-to-end.**

- The full RAG core (ingestion, embeddings, hybrid retrieval, reranking, context construction,
  grounded generation, citation validation, safety pre/post-check, multi-domain segmentation) is
  live in [`backend/app/rag/pipeline.py`](./backend/app/rag/pipeline.py)'s `answer_query()`, backed
  by a complete FastAPI HTTP layer (auth, onboarding, chat, knowledge, recommendations, admin,
  evaluation, privacy).
- **Live provider integration is verified**, not just mocked: real Groq (`openai/gpt-oss-120b`)
  chat completions and real Gemini (`gemini-embedding-001`) embeddings have both been exercised
  end-to-end against the actual APIs, including the full `answer_query()` pipeline producing a
  cited, grounded answer and correctly short-circuiting to "insufficient evidence" when the
  knowledge base has nothing relevant.
- The full product frontend (Next.js) is built: landing, auth, onboarding, dashboard, AI chat with
  citations and evidence-level badges, nutrition/lifestyle/ayurveda/stage-wise guidance pages,
  recommendations, a sources explorer, settings/privacy, and admin dashboards for document and
  evaluation management — all wired to the real backend API.
- **238 automated tests pass** across `backend/` (175), `ingestion/` (27), and `evaluation/` (36);
  the frontend builds cleanly with zero lint/type errors across all 17 routes.
- The full local stack (PostgreSQL/pgvector, Redis, FastAPI, Next.js) runs via Docker Compose, and
  each service's production Dockerfile has been built and smoke-tested independently.

**Known, honestly-reported limitation:** the hallucination/grounding evaluation suite
(`evaluation/hallucination/`) currently passes 3 of 11 out-of-corpus test questions — see
[Limitations](#limitations) below and `PROGRESS.md` (2026-09-24, issue #19) for the investigation.
This is a real, measured gap in retrieval precision, not a documentation placeholder.

---

## Problem

Pregnant women navigating nutrition, lifestyle, and traditional-practice questions get answers from
generic sources that blend modern medical evidence with unverified traditional claims — without
ever showing which is which, how strong the evidence is, or when to see a doctor instead of asking
an app.

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

Core principles: **evidence first**, retrieval before generation, safety before personalization,
personalization never overrides safety, and traditional/Ayurvedic knowledge is always explicitly
labelled and never silently equated with modern medical evidence.

---

## Architecture

```
                     ┌──────────────────────┐
                     │       Frontend        │
                     │     Next.js 16 UI     │
                     └───────────┬───────────┘
                                 │ HTTPS / REST (JWT)
                                 ▼
                     ┌──────────────────────┐
                     │        FastAPI        │
                     │        Backend        │
                     └───────────┬───────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                   ▼
      ┌──────────────┐   ┌──────────────┐   ┌────────────────┐
      │  PostgreSQL  │   │  RAG Engine  │   │  Safety Engine  │
      │  + pgvector  │   │  Retrieval   │   │  Rules / Risk   │
      └──────────────┘   │  Reranking   │   │  Escalation     │
                          └──────┬───────┘   └────────────────┘
                                 │
                                 ▼
                          ┌──────────────┐
                          │ LLM (Groq) +  │
                          │ Embeddings    │
                          │ (Gemini)      │
                          └──────┬───────┘
                                 ▼
                         Answer + Citations
```

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS, shadcn/ui-style components |
| Backend | Python 3.11, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Database | PostgreSQL |
| Vector search | pgvector |
| Cache / rate limiting | Redis |
| LLM (generation) | Groq (`openai/gpt-oss-120b`) |
| Embeddings | Gemini (`gemini-embedding-001`) |
| Document processing | PyMuPDF, python-docx |
| Auth | JWT |
| Containers | Docker, Docker Compose |
| Testing | pytest, Playwright, ruff, mypy, eslint |

Deliberately **not** used at this stage: microservices, Kubernetes, fine-tuning/custom model
training, multiple vector databases, multiple orchestration frameworks. This is a modular monolith
by design — the pieces are cleanly separated (RAG, safety, API, ingestion, evaluation) without the
operational overhead a distributed system would add at this scale.

---

## Project Structure

```
matriva/
├── frontend/             Next.js app — landing, auth, onboarding, dashboard, chat,
│                         nutrition/lifestyle/ayurveda/guidance, recommendations,
│                         sources explorer, settings, admin (documents, evaluation)
├── backend/
│   ├── app/
│   │   ├── api/          FastAPI routers: auth, profile, chat, knowledge, admin,
│   │   │                 evaluation, recommendations, privacy, feedback, demo
│   │   ├── models/       SQLAlchemy application models + evidence/guideline metadata
│   │   ├── schemas/      API request/response schemas + canonical RAG knowledge schemas
│   │   ├── rag/          Full RAG pipeline (retrieval, reranking, context, grounding,
│   │   │                 embeddings) + the SQLAlchemy/API adapter
│   │   ├── safety/       Independent classifier, post-check, prompt-injection defense
│   │   ├── services/     Auth, profile, chat, recommendation, admin, privacy, evaluation
│   │   └── core/         Config, database, security, rate limiting, observability
│   ├── tests/            175 backend unit/integration/RAG regression tests
│   └── scripts/          pgvector live verification, secret scan
├── knowledge/
│   ├── seed/seed.yaml    Curated seed knowledge set (demo corpus)
│   └── ayurveda/         Source PDF + OCR text extract
├── ingestion/            Parser, chunker, quality-check pipelines — 27 tests
├── evaluation/           Retrieval/generation/safety/hallucination eval harnesses,
│                         datasets, reports/ — 36 tests
├── database/             Migrations, seed script
├── docs/                 Architecture, API, RAG, safety, deployment, compliance docs
└── docker-compose.yml
```

---

## Getting Started

### Prerequisites
- Docker + Docker Compose
- Node.js 20+
- Python 3.11+
- A Groq API key and a Gemini API key (optional — the app runs in a safe local grounded-fallback
  mode without them, useful for development without live provider costs)

### Environment variables

Copy `.env.example` to `.env` and set a unique `JWT_SECRET` (at least 32 characters, generate with
`python -c "import secrets; print(secrets.token_urlsafe(48))"`). `.env` is gitignored — never
commit real secrets. `DEMO_MODE` must be `false` in production.

```bash
cp .env.example .env
```

### Run the full stack

```bash
# Postgres/pgvector + Redis + FastAPI + Next.js, all together
docker compose up --build
```

Or run each service directly for faster local iteration:

```bash
# Backend
cd backend
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head
python ../database/seed/seed.py     # optional synthetic demo data
uvicorn app.main:app --reload       # http://localhost:8000  (docs at /docs)

# Frontend
cd frontend
npm install
cp .env.example .env.local          # set NEXT_PUBLIC_API_URL
npm run dev                          # http://localhost:3000
```

The production-oriented compose file is `docker-compose.prod.yml`; see
[`docs/deployment.md`](./docs/deployment.md) and [`frontend/README.md`](./frontend/README.md)
before deploying.

### Run knowledge ingestion

```bash
cd ingestion
python -m pipelines.run --source ../knowledge/ayurveda
```

### Run the tests

```bash
# Backend: tests, lint, type-check, secret scan
cd backend
pytest -q
ruff check .
mypy app/
python scripts/secret_scan.py --root ..

# Ingestion
cd ../ingestion && pytest tests/

# Evaluation harnesses
cd ../evaluation && pytest tests/

# Frontend: lint, type-check, production build, e2e
cd ../frontend
npm run lint && npm run typecheck && npm run build
npx playwright install --with-deps chromium && npm run test:e2e
```

### Run evaluation harnesses

Each writes a JSON report to `evaluation/reports/`. Generation and live-pipeline checks use
`LLM_API_KEY`/`GROQ_API_KEY` when set; without one they run in a self-test mode against curated
example responses instead of live model output.

```bash
cd evaluation
python -m retrieval.run       # Recall@K, Precision@K, MRR, nDCG@K
python -m generation.run      # groundedness, citation correctness, relevance, completeness
python -m safety.run          # safety classifier routing correctness (21 test cases)
python -m hallucination.run   # out-of-corpus questions -> must return "insufficient evidence"
```

### Verify pgvector against a real Postgres instance

The automated test suite exercises an in-memory vector store double. To check the real
pgvector-backed implementation against a live database:

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

- Full backlog is tracked as GitHub Issues across milestones (`M1: Foundation + RAG Core`,
  `M2: Personalization + Safety + Domain Engines`, `M3: Frontend + Admin + Evaluation + Deploy`).
- Every feature in [`docs/FEATURES.md`](./docs/FEATURES.md) maps to a tracked issue.
- Ownership/review routing is enforced via [`.github/CODEOWNERS`](./.github/CODEOWNERS).
- **After every meaningful change, add a short entry to [`PROGRESS.md`](./PROGRESS.md)** so the
  team always knows real project status without digging through git log.

---

## Limitations

- **Prototype-stage knowledge base**: seeded from a small curated set of sources
  (`knowledge/seed/seed.yaml`), not comprehensive coverage of any domain.
- **Clinical rules require sign-off**: this codebase does not invent or certify medical thresholds.
  Ayurvedic content is explicitly marked `PENDING_CLINICAL_REVIEW` until a Clinical Lead signs off.
- **Retrieval precision gap, honestly measured**: the hallucination/grounding suite
  (`evaluation/hallucination/`) currently passes only 3 of 11 out-of-corpus questions — a question
  on a related-but-uncovered topic can retrieve a loosely-matching chunk and get an attempted
  answer instead of an "insufficient evidence" response. This is tracked as open issue #19; see
  `PROGRESS.md` (2026-09-24) for the investigation.
- **Branch protection is not yet enabled** on `main` (tracked as open issue #21) — CODEOWNERS
  routing exists, but merges are not currently gated by required review/CI in GitHub settings.
- Not a substitute for professional medical advice, diagnosis, or emergency care at any stage.

## Safety Considerations

- Safety classification is an **independent module**, never delegated solely to the LLM.
- If the safety subsystem fails, the system **fails closed** — it will not return an unrestricted
  medical recommendation.
- Traditional/Ayurvedic content is always labelled and never presented as having the same evidence
  status as modern medical guidance unless explicitly supported by a reviewed source.
- Retrieved document content is always treated as **data, never as instructions**
  (prompt-injection defense).
