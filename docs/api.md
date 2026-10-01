# Backend API

The backend is a FastAPI service. Interactive OpenAPI documentation is available at `/docs`
in development and `/redoc` at `/redoc`.

Base URL: `http://localhost:8000` (Docker Compose default; the README's local `uvicorn` example uses `8010`).

## Authentication

Protected endpoints use `Authorization: Bearer <access-token>`.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/auth/register` | Create a user and return a short-lived JWT |
| `POST` | `/auth/login` | Verify credentials and return a JWT |
| `GET` | `/auth/me` | Return the authenticated user |

Passwords are hashed with PBKDF2-HMAC-SHA256 and a random salt. JWTs are HMAC-signed,
time-limited, issuer/audience checked, and never contain profile or health data.

## Profile and pregnancy

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/profile` | Read the caller's stored profile |
| `PUT` | `/profile` | Store/update profile data after explicit consent |
| `DELETE` | `/profile` | Delete profile and health data |
| `GET` | `/pregnancy` | Read pregnancy week/stage |
| `PUT` | `/pregnancy` | Store pregnancy week after consent |
| `DELETE` | `/pregnancy` | Delete pregnancy profile |
| `POST` | `/privacy/consent` | Grant or withdraw consent |
| `GET` | `/privacy/export` | Export the caller's data as JSON |
| `DELETE` | `/privacy/account` | Delete the account and associated data |

A chat message never silently updates the permanent profile. Session context is stored only
on the conversation.

## Chat and recommendations

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/chat` | Evidence-grounded chat; unauthenticated only when `DEMO_MODE=true` |
| `POST` | `/chat/stream` | Same pipeline, streamed as server-sent events |
| `GET` | `/chat/history` | Read an authenticated user's conversation history |
| `POST` | `/recommendations/generate` | Generate explainable recommendations |
| `GET` | `/recommendations` | List the caller's recommendations |
| `POST` | `/recommendations/{id}/save` | Save a recommendation |
| `DELETE` | `/recommendations/{id}/save` | Unsave a recommendation |
| `POST` | `/feedback` | Rate a message or recommendation |

The chat response contains `answer`, `intent`, `safety_status`, `sources`, `citations`,
`evidence`, and `recommendations`. If the safety subsystem, retrieval layer, or source set is
unavailable, the service returns a safe fallback or `503`; it never returns an unrestricted
medical answer.

## Care features (`/care`, authenticated)

All care data is consent-gated and removed by consent withdrawal, profile deletion, account
deletion, and included in `/privacy/export`. Rules (thresholds, visit weeks, red-flag questions)
come from `backend/app/data/care_rules.yaml`, each with a source and
`pending_clinical_review` status.

| Method | Path | Purpose |
|---|---|---|
| `PUT` | `/care/dating` | Set last period, due date, or current week; the week then advances on its own |
| `GET` | `/care/plan` | Exact week/day, due date, visit calendar, supplements, this week's tasks |
| `GET` | `/care/reminders` | Rule-based reminders (e.g. today's top reminder) |
| `PUT` / `GET` | `/care/checkin` | Save / read the daily check-in (mood, symptoms, movement, iron tablet) |
| `GET` | `/care/checkin/summary` | Streaks and adherence |
| `POST` / `GET` | `/care/readings` | Add / list Hb, BP, weight, sugar readings with sourced flags |
| `DELETE` | `/care/readings/{id}` | Delete a reading |
| `POST` | `/care/readings/parse-report` | Parse pasted lab-report text into readings (for confirmation) |
| `POST` | `/care/readings/ocr` | Same from a photo (needs `tesseract` on the server) |
| `POST` / `GET` | `/care/meals` | Log / list meals with approximate nutrients and daily gaps |
| `DELETE` | `/care/meals/{id}` | Delete a meal |
| `GET` | `/care/screening/questions` | Red-flag questions filtered by week |
| `POST` | `/care/screening/assess` | Triage result: emergency / urgent / soon, with sources |
| `GET` | `/care/summary` | One-page doctor summary |
| `PUT` / `GET` / `DELETE` | `/care/emergency-contact` | Manage the emergency contact |

Daily wellness logs live under `/wellness` (`PUT`/`GET /wellness/daily`, `GET /wellness/summary`),
and the curated video/article/paper library under `GET /resources`.

## Knowledge and sources

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/knowledge/search` | Search approved chunks with domain/stage/region filters |
| `GET` | `/knowledge/food` | Search food records by region and diet |
| `GET` | `/knowledge/lifestyle` | List lifestyle/activity guidance |
| `GET` | `/sources/{id}` | Return full source/evidence metadata |
| `GET` | `/ayurveda/sources/{id}` | Return Ayurveda provenance |
| `GET` | `/guidelines` | List active guideline registry entries |
| `GET` | `/knowledge/graph` | Concept graph around a query (`?q=iron`), derived from approved text |
| `GET` | `/knowledge/book` | Prasuti Tantra structure: chapters, sections, authorities |
| `GET` | `/knowledge/book/glossary` | Hindi ↔ English glossary from the book |

Only approved/active knowledge is returned to ordinary users. Page/section locators are
returned only when stored in the source record; the API does not invent them.

## R0 demo endpoints

When `DEMO_MODE=true`:

- `POST /chat` accepts a message without a token for the synthetic demo profile.
- `GET /pregnancy/next-visit?current_week=N` returns the next configured ANC contact week.

The demo seed records are explicitly synthetic and must not be presented as a complete or
current clinical guideline.

## Administration and evaluation

Administrator-only routes are under `/admin`: document upload/review/reindex/bulk-approve, food and
lifestyle records, Ayurveda provenance, guideline registry, safety rules, safety events, and
audit logs. Staff routes under `/evaluation` run and retrieve evaluation reports.

## Errors and limits

- `401`: missing/invalid authentication
- `403`: authenticated but not authorized
- `404`: resource not found or not visible
- `409`: workflow conflict, such as approving an unindexed document
- `413`: upload exceeds the configured limit
- `415`: unsupported upload type
- `422`: invalid input
- `429`: rate limit exceeded

Other routes: `GET /health` (app and database) and staff-only `GET /internal/metrics`.
- `503`: safety or required dependency unavailable (fail closed)
