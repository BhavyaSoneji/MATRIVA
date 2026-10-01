# MATRIVA backend

FastAPI, SQLAlchemy and Alembic. The rest of the project is described in the [root README](../README.md) and [`docs/`](../docs/README.md); this page is the map for working in `backend/`.

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp ../.env.example .env            # set JWT_SECRET to 32+ random characters
alembic upgrade head
uvicorn app.main:app --reload --port 8010     # http://localhost:8010/docs
```

No API key is needed: `RAG_ENGINE=local` is the default. Settings are listed in [`../docs/configuration.md`](../docs/configuration.md).

## Layout

| Path | What is in it |
|---|---|
| `app/main.py` | App, middleware (request id, rate limit, security headers), routers, health and metrics. Loads the guard-rail registry at start-up |
| `app/api/` | Routers: auth, profile, chat, care, knowledge, recommendations, resources, wellness, privacy, feedback, admin, evaluations |
| `app/services/` | Orchestration. `chat.py` runs the request path; `care/` holds dating, plan, screening, tracking, readings, meals, food guide, summary, privacy |
| `app/safety/` | Pre-check, post-check, prompt-injection defence |
| `app/safety/guardrails/` | The rule engine: `registry.py` (load and validate), `engine.py` (match), `context.py` (what we know about the person), `output.py` (check the answer) |
| `app/rag/local/` | The offline retrieval engine |
| `app/rag/`, `app/llm/` | LangChain orchestration plus the optional Groq and Gemini providers |
| `app/data/` | Data that is reviewed as data: `guardrails/*.yaml`, `care_rules.yaml`, `food_guide.yaml`, `ontology.yaml`, `book_index.json`, `foods_nutrients.json`, `library.yaml` |
| `app/models/`, `app/schemas/` | SQLAlchemy entities and Pydantic contracts |
| `alembic/versions/` | Migrations `0001` to `0005` |
| `scripts/` | `ingest_real_knowledge.py`, `build_book_index.py`, `secret_scan.py`, `verify_pgvector_live.py` |
| `tests/` | 534 tests |

## Scripts

```bash
python scripts/ingest_real_knowledge.py [--book-only | --seed-only] [--replace] [--dry-run]   # loads as PENDING
python scripts/build_book_index.py                       # book structure, authorities, glossary
python scripts/secret_scan.py --root ..                  # also run in CI
python -m app.safety.guardrails                          # prints what the guard rails contain
```

Everything `ingest_real_knowledge.py` inserts is **pending**: an admin approves documents in Admin, Documents before they can answer.

## Common tasks

| To | Do |
|---|---|
| Add a medicine, herb, food or warning sign | Edit a file in `app/data/guardrails/`, run `pytest tests/test_guardrails.py`, see [`../CONTRIBUTING.md`](../CONTRIBUTING.md) |
| Change a threshold or visit week | Edit `app/data/care_rules.yaml` |
| Add a column or table | Change the model, then write a migration that **checks what exists first** (copy `alembic/versions/0005_safety_profile.py`): `0001` builds the current models on a fresh database, so a later migration must be safe to re-run. `tests/test_migrations.py` proves a fresh database reaches head |
| Add an endpoint | Router in `app/api/`, logic in `app/services/`, schema in `app/schemas/`, a test, and a row in [`../docs/api.md`](../docs/api.md) |
| Run the checks | `pytest -q && ruff check . && mypy app/` |

`ruff` is pinned in `requirements-dev.txt`. Some files outside the areas below have existing `ruff` and `mypy` findings; keep your own changes clean.
