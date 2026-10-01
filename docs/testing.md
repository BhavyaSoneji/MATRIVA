# Testing

What is tested, how to run it, and what a passing run does and does not prove.

| Suite | Where | Tests | Run |
|---|---|---:|---|
| Backend | `backend/tests/` | 534 | `cd backend && pytest -q` |
| Ingestion | `ingestion/tests/` | 43 | `cd ingestion && pytest tests/` |
| Evaluation harnesses | `evaluation/tests/` | 36 | `cd evaluation && pytest tests/` |
| Frontend end-to-end | `frontend/tests/e2e/` | 12 | `cd frontend && npx playwright test` |

Static checks: `ruff check .` and `mypy app/` (backend), `npm run lint`, `npm run typecheck` and `npm run build` (frontend), `python scripts/secret_scan.py --root ..`, and `npm audit --omit=dev`. CI runs all of them on every pull request ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)).

## Backend

The backend tests use a SQLite file that is dropped and recreated for every test, with real FastAPI requests through `TestClient`. Provider keys are blanked in `conftest.py`, so no test can reach Groq, Gemini or the web.

| Area | Files |
|---|---|
| Auth, profile, privacy | `test_auth_profile.py`, `test_admin_privacy.py` |
| Chat, streaming, intent, follow-ups | `test_chat_*.py`, `test_pipeline_*.py`, `test_intent_classification.py` |
| Retrieval and the offline engine | `test_local_rag*.py`, `test_retrieval.py`, `test_reranking.py`, `test_vector_store.py` |
| Safety: pre- and post-check, injection, languages | `test_classifier.py`, `test_pre_check.py`, `test_post_check.py`, `test_prompt_injection.py`, `test_multilingual_safety.py` |
| **Guard rails** | `test_guardrails.py` |
| Care features | `test_care.py`, `test_wellness.py` |
| **Food guide** | `test_food_guide.py` |
| Migrations | `test_migrations.py` (a fresh database upgrades to head) |

### What the guard-rail tests prove

- The registry loads, ids are unique, every source key exists, and every rule has a message and a source.
- Every emergency rule has Hindi and Gujarati text, and every medicine class is translated.
- A phrase triggers one rule per kind, so a broad group and a single drug never both fire.
- Real questions route as intended (a table of about 45 in English, Hinglish, Hindi and Gujarati), including typos.
- **No ordinary question in the retrieval benchmarks is blocked.** This is the test that catches a guard rail that cries wolf.
- Personal rules use the profile, week gating works, and an unknown week never hides a warning.
- Unsafe answers are replaced and ordinary sourced answers pass.
- Through the real `/chat` and `/chat/stream` endpoints: a medicine question gets no retrieval and no advice, and the new profile fields are stored, validated, exported and deleted.

### What the food-guide tests prove

- Every quoted entry from the book really appears in the OCR text of the book, so nothing is invented.
- Medicated preparations and enemas are never listed as food; vegetarian and vegan filters, allergies and "never liver" hold.
- Nutrient amounts equal the USDA value times the serving, and dry grains use a dry serving.

## Retrieval quality is measured, not only tested

`evaluation/local_rag/` holds four question sets. Only the last one is a clean test, because the others were used to diagnose and fix failures.

```bash
python evaluation/local_rag/run.py          # hit@1, hit@3, MRR, refusal precision per set
python evaluation/local_rag/ablation.py     # what each retrieval signal is worth
```

`backend/tests/test_local_rag_eval.py` fails CI if the development sets regress. Results and failure modes are in [`local-rag.md`](./local-rag.md).

## End-to-end

The Playwright specs mock the API, so they check the interface and its contract with the backend, not the backend. They cover the chat workspace, readings, meals, the food guide, the caution callout and its source, and the Settings safety profile saving without erasing other fields.

Playwright's `webServer` runs `npm run build && npm run start` on port 3000 and **reuses a server that is already listening there**. A stale server will make a passing test run against old code. Stop it first, or run in CI mode.

## What a green run does not prove

- That the clinical content is correct. Rules and thresholds are sourced but unreviewed ([`clinical-review.md`](./clinical-review.md)).
- That Hindi and Gujarati wording is natural.
- That real users behave like the test questions. The held-out sets are written by the team.
