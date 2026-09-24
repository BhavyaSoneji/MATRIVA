# Backend API

The backend is a FastAPI service. Interactive OpenAPI documentation is available at `/docs`
in development and `/redoc` at `/redoc`.

Base URL: `http://localhost:8000`

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

## Knowledge and sources

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/knowledge/search` | Search approved chunks with domain/stage/region filters |
| `GET` | `/knowledge/food` | Search food records by region and diet |
| `GET` | `/knowledge/lifestyle` | List lifestyle/activity guidance |
| `GET` | `/sources/{id}` | Return full source/evidence metadata |
| `GET` | `/ayurveda/sources/{id}` | Return Ayurveda provenance |
| `GET` | `/guidelines` | List active guideline registry entries |

Only approved/active knowledge is returned to ordinary users. Page/section locators are
returned only when stored in the source record; the API does not invent them.

## R0 demo endpoints

When `DEMO_MODE=true`:

- `POST /chat` accepts a message without a token for the synthetic demo profile.
- `GET /pregnancy/next-visit?current_week=N` returns the next configured ANC contact week.

The demo seed records are explicitly synthetic and must not be presented as a complete or
current clinical guideline.

## Administration and evaluation

Administrator-only routes are under `/admin`: document upload/review/reindex, food and
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
- `503`: safety or required dependency unavailable (fail closed)
