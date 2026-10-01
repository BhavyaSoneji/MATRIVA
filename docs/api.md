# Backend API

The backend is a FastAPI service. Interactive OpenAPI documentation is available at `/docs`
in development and `/redoc` at `/redoc`.

Base URL: `http://localhost:8000` (Docker Compose default; the README's local `uvicorn` example uses `8010`).

## Conventions

| | |
|---|---|
| **Format** | JSON requests and responses, UTF-8. Hindi and Gujarati text is sent as is |
| **Auth** | `Authorization: Bearer <token>` from `/auth/register` or `/auth/login`. The token lasts 30 minutes by default |
| **Errors** | `{"detail": "..."}` for a message, or `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` for validation errors (`422`) |
| **Request id** | Every response carries `X-Request-ID`. Send your own (up to 64 characters) to correlate with the logs |
| **Rate limits** | `429` with a `Retry-After` header on auth, chat and the knowledge routes ([`configuration.md`](./configuration.md)) |
| **Caching** | Responses are `Cache-Control: no-store` |
| **CORS** | Only origins in `CORS_ORIGINS`; methods GET, POST, PUT, DELETE, OPTIONS |
| **Health** | `GET /health` returns `{"status": "ok", "database": "ok", "redis": "not_configured", "version": "0.1.0"}` |
| **Interactive docs** | `/docs` (Swagger UI) and `/redoc` in development |

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

The profile also carries the safety profile used by the guard rails: `known_conditions`, `current_medications`, `allergies`, `risk_factors` (codes from `backend/app/data/guardrails/conditions.yaml`), `age_years` and `blood_group` (`A+`, `O-`...). `PUT /profile` replaces the whole profile, so send every field you want to keep.

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
`evidence`, `recommendations` and `suggestions`. `evidence.guardrails` lists the guard-rail rules that applied (id, kind, action, title, the phrase that matched, and sources with links). A caution is a line beginning `⚠️` at the start of `answer`. If the safety subsystem, retrieval layer, or source set is
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
| `GET` | `/care/food-guide` | The book's food regimen for this month (`?month=1..9` to choose one) and, with `?need=` one of `iron`, `calcium`, `protein`, `folate`, `vitamin_c`, `vitamin_b12`, `zinc`, `magnesium`, `vitamin_a`, `fibre`, the foods richest in that nutrient. Respects diet and allergies. Foods only |
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

## Streaming chat

`POST /chat/stream` takes the same body as `/chat` and answers with server-sent events (`text/event-stream`). The safety pre-check, guard rails, retrieval, output check and post-check are exactly the ones `/chat` uses.

| Event | Data | Meaning |
|---|---|---|
| `delta` | `{"text": "..."}` | Append to the displayed answer. Zero or more before `final`. A refusal, an emergency message, or a composed answer from the offline engine arrives as one delta |
| `final` | `{"answer", "safety_status", "citations", "corrected"}` | Sent once, after validation. **If `corrected` is `true`, discard what you rendered from the deltas and show `answer`**: a caution notice was put in front, or the answer was replaced. If `false`, `answer` equals the deltas joined |
| `done` | `{"conversation_id", "message_id", "sources", "evidence", "recommendations", "suggestions"}` | Sent last, once the conversation is saved. Metadata only |
| `error` | `{"answer": "..."}` | Sent instead of the others if the safety layer is unavailable or the server fails after the stream began; the stream ends |

```
event: delta
data: {"text": "Doctors usually advise avoiding ibuprofen in pregnancy ..."}

event: final
data: {"answer": "Doctors usually advise ...", "safety_status": "high_risk", "citations": [], "corrected": false}

event: done
data: {"conversation_id": "...", "message_id": "...", "sources": [], "evidence": {...}, "recommendations": [], "suggestions": []}
```

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

## Examples

Sign up, send a message, and read what the guard rails did. Replace the host with yours.

```bash
# 1. Register (returns access_token)
curl -s localhost:8000/auth/register -H 'content-type: application/json' \
  -d '{"email":"asha@example.com","password":"StrongPass123","full_name":"Asha"}'

TOKEN=...   # the access_token from above

# 2. Give consent and a condition, then your week
curl -s -X PUT localhost:8000/profile -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"consent":true,"consent_version":"v1.0","diet_type":"vegetarian","known_conditions":["high blood pressure"]}'
curl -s -X PUT localhost:8000/care/dating -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"current_week":21}'

# 3. Ask a medicine question
curl -s localhost:8000/chat -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"message":"Can I take ibuprofen for backache?"}'
```

The medicine question is refused: `safety_status` is `high_risk`, `sources` and `citations` are empty because nothing was retrieved, and the rule that fired is in `evidence.guardrails`:

```json
{
  "safety_status": "high_risk",
  "answer": "Doctors usually advise avoiding ibuprofen in pregnancy (NSAID pain relievers can harm the baby's kidneys ...). I can't advise on medicines: only your doctor can decide ...",
  "evidence": {
    "safety_reason": "Matched guard-rail rule: Ibuprofen",
    "guardrails": [{
      "id": "med-ibuprofen", "kind": "medication", "action": "block", "title": "Ibuprofen", "matched": "ibuprofen",
      "sources": [{"key": "nhs-medicines", "name": "NHS - Medicines in pregnancy", "url": "https://www.nhs.uk/pregnancy/keeping-well/medicines/"}]
    }]
  }
}
```

```bash
# 4. What to eat this month, for iron
curl -s "localhost:8000/care/food-guide?need=iron" -H "authorization: Bearer $TOKEN"
```

```json
{
  "week": 21, "month": 5, "diet": "vegetarian",
  "traditional": {
    "evidence_level": "traditional",
    "foods": [{"authority": "Caraka and Vagbhata I", "text": "Ghrta prepared with butter extracted from milk.", "page": 136, "paraphrased": false}]
  },
  "modern": {
    "need": {"id": "iron", "label": "Iron", "unit": "mg", "daily_allowance": 27},
    "foods": [{"name": "Soybeans", "category": "legume", "serving_g": 150, "amount": 7.7, "percent": 29}]
  }
}
```

(Both responses are shortened.) An unknown `need` returns `422 {"detail": "Unknown need: nope"}`; no token returns `401`.

## Errors and limits

- `401`: missing/invalid authentication
- `403`: authenticated but not authorized
- `404`: resource not found or not visible
- `409`: workflow conflict, such as approving an unindexed document
- `413`: upload exceeds the configured limit
- `415`: unsupported upload type
- `422`: invalid input
- `429`: rate limit exceeded (read `Retry-After`)

Other routes: `GET /health` (app and database) and staff-only `GET /internal/metrics`.
- `503`: safety or required dependency unavailable (fail closed)
