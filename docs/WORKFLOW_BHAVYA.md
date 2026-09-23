# Backend Workflow — Bhavya

Step-wise execution order for all backend issues (`backend` label, assignee `@BhavyaSoneji`).
Work top to bottom. Don't start a step until its "Depends on" column is actually done — check
[`PROGRESS.md`](../PROGRESS.md) for real status before jumping ahead.

## Sprint 0 — Health-a-thon Round 1 (due Sep 25)

Do these first, in this order. Nothing below this section matters until Round 0 ships.

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 1 | [#69](https://github.com/BhavyaSoneji/MATRIVA/issues/69) Minimal `/chat` endpoint | Accept a message, call Neev's retrieval+Groq script directly (skip service/repository layering), return `answer + sources`. Hard-code one demo profile (2nd trimester, vegetarian, region) — no onboarding flow yet | Neev's #66 |
| 2 | [#70](https://github.com/BhavyaSoneji/MATRIVA/issues/70) ANC visit-schedule endpoint | `GET /pregnancy/next-visit` returning next due visit from the FOGSI 8-contact weeks (12/20/26/30/34/36/38/40/41), given the hard-coded demo profile's current week | — |
| 3 | [#71](https://github.com/BhavyaSoneji/MATRIVA/issues/71) Wire both endpoints for the demo | CORS enabled, quick run instructions, confirm Raj's frontend can hit both locally without auth | Steps 1-2 |

### Step 1 detail — #69 minimal `/chat`
1. Minimal FastAPI app (just enough to run — full scaffold is step 4 in Sprint 1, don't over-build now).
2. `POST /chat` body `{ message: string }`.
3. Call into Neev's script (from #66) directly — a plain function import is fine, no message queue,
   no background job.
4. Return `{answer, sources[], evidence_label}` exactly as Neev's script produces it — the frontend
   (#72) expects this shape.
5. No auth, no DB persistence required for Round 0.

### Step 2 detail — #70 ANC visit-schedule endpoint
1. `GET /pregnancy/next-visit` — hard-code the demo profile's current week (or accept it as a query
   param if trivial).
2. Deterministic lookup against `[12, 20, 26, 30, 34, 36, 38, 40, 41]` — return the next week >=
   current week.
3. Response: `{ next_visit_week: number }`.

### Step 3 detail — #71 wire for demo
1. Enable permissive CORS for local dev (`localhost:3000`).
2. One paragraph in the repo README or a `backend/RUN.md`: how to start the server (`uvicorn ...`).
3. Confirm both endpoints respond correctly via `curl` before handing off to Raj.

**Coordination point:** Step 1 is blocked on Neev's #66 (minimal retrieval + Groq script) existing
as a callable function. If Neev isn't ready yet, stub `/chat` to return a hard-coded example
response matching the expected shape so Raj can build against it, then swap in the real call.

---

## Sprint 1 — Foundation (if shortlisted, build sprint Oct 5 - Nov 8)

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 4 | [#23](https://github.com/BhavyaSoneji/MATRIVA/issues/23) Scaffold FastAPI app structure | Full `api/models/schemas/services/repositories/rag/safety/recommendation/personalization/llm/evidence/utils` layout per Section 6 (upgrades the Sprint 0 minimal app) | — |
| 5 | [#24](https://github.com/BhavyaSoneji/MATRIVA/issues/24) Docker Compose | Postgres+pgvector, Redis, backend service, `.env.example` | #23 |
| 6 | [#25](https://github.com/BhavyaSoneji/MATRIVA/issues/25) SQLAlchemy models | Core tables: users, pregnancy_profiles, health/lifestyle/dietary/cultural_profiles, conversations, messages, knowledge_documents, knowledge_chunks, knowledge_sources, evidence_metadata | #23 |
| 7 | [#26](https://github.com/BhavyaSoneji/MATRIVA/issues/26) Alembic migrations + seed script | `alembic upgrade head` from empty DB, seed 3 demo profiles | #24, #25 |

## Sprint 1 — Auth & Onboarding

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 8 | [#27](https://github.com/BhavyaSoneji/MATRIVA/issues/27) Auth: register/login (JWT) | `/auth/register`, `/auth/login`, hashed passwords, JWT issuance | #26 |
| 9 | [#28](https://github.com/BhavyaSoneji/MATRIVA/issues/28) Onboarding APIs | `GET/PUT /profile`, `GET/PUT /pregnancy`, consent required, update/delete support | #27 |

## Sprint 1 — Core Chat & Domain Engines

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 10 | [#29](https://github.com/BhavyaSoneji/MATRIVA/issues/29) Full `/chat` endpoint | Upgrades Sprint 0's #69: authenticate -> load profile -> classify intent -> safety pre-check -> retrieve -> rerank -> personalize -> generate -> safety post-check -> validate citations -> persist conversation/messages | #9, Neev's RAG pipeline (#1-#11) |
| 11 | [#31](https://github.com/BhavyaSoneji/MATRIVA/issues/31) Pregnancy stage engine | Deterministic week -> trimester -> stage label, fully unit tested | #26 |
| 12 | [#30](https://github.com/BhavyaSoneji/MATRIVA/issues/30) Recommendation engine | Profile -> stage -> intent -> retrieval -> eligibility filter -> safety filter -> ranking; every rec stores its "why shown" reason | #31, Neev's #11 |
| 13 | [#32](https://github.com/BhavyaSoneji/MATRIVA/issues/32) Food/regional engine | `food_items`/`food_regions` model + `GET /knowledge/search` region/diet filters; evidence_status and safety kept separate | #26 |
| 14 | [#59](https://github.com/BhavyaSoneji/MATRIVA/issues/59) Lifestyle engine | `exercise_guidance` content model, filtered through restrictions/safety | #26 |
| 15 | [#33](https://github.com/BhavyaSoneji/MATRIVA/issues/33) Ayurveda source storage API | `ayurvedic_sources` table with full provenance, `GET /sources/{id}` | #26, Neev's #15 |
| 16 | [#62](https://github.com/BhavyaSoneji/MATRIVA/issues/62) Knowledge search & sources API | `GET /knowledge/search` with stage/domain/region filters, `GET /sources/{id}` full evidence metadata | #32, #33 |
| 17 | [#60](https://github.com/BhavyaSoneji/MATRIVA/issues/60) Conversation memory | Session context kept separate from permanent profile; no silent profile mutation from chat | #29 |
| 18 | [#63](https://github.com/BhavyaSoneji/MATRIVA/issues/63) Feedback API | `POST /feedback` tied to message/recommendation id | #29 |

## Sprint 1 — Privacy, Safety, Reliability

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 19 | [#37](https://github.com/BhavyaSoneji/MATRIVA/issues/37) Privacy: consent, export, deletion | Delete/anonymize account+health data, structured data export | #28 |
| 20 | [#38](https://github.com/BhavyaSoneji/MATRIVA/issues/38) Error handling + fail-closed fallback | Defined fallback for every external dependency failure; safety-subsystem failure must fail closed | #29, Neev's #12-#14 |
| 21 | [#61](https://github.com/BhavyaSoneji/MATRIVA/issues/61) Security hardening | Rate limiting on auth+chat, Pydantic validation everywhere, `audit_logs` on sensitive actions | #27, #37 |

## Sprint 1 — Admin & Ops

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 22 | [#34](https://github.com/BhavyaSoneji/MATRIVA/issues/34) Admin APIs: document management | Upload -> pending review -> approve -> active; reindex endpoint | #25, Neev's ingestion pipeline |
| 23 | [#35](https://github.com/BhavyaSoneji/MATRIVA/issues/35) Admin APIs: safety rules management | CRUD `safety_rules`, queryable `safety_events` | #25, Neev's #12-#13 |
| 24 | [#36](https://github.com/BhavyaSoneji/MATRIVA/issues/36) Evaluation run APIs | `POST /evaluation/run`, `GET /evaluation/results`, wired to Neev's eval scripts | Neev's #16-#20 |
| 25 | [#39](https://github.com/BhavyaSoneji/MATRIVA/issues/39) Observability | Latency/error/safety-classification logging on `/chat`, no PII in logs | #29 |
| 26 | [#40](https://github.com/BhavyaSoneji/MATRIVA/issues/40) Dockerize for production | Prod Dockerfile, secrets via env, HTTPS-ready config | #24, #61 |
