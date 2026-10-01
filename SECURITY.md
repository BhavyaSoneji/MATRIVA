# Security

MATRIVA handles pregnancy and health information. Please report problems responsibly.

## Reporting a vulnerability

Do **not** open a public issue with details of a vulnerability. Use GitHub's **private vulnerability reporting** on this repository (Security tab, "Report a vulnerability") if it is enabled, or contact the maintainer [@neevmodh](https://github.com/neevmodh) directly through GitHub and ask for a private channel. Please include what you found, how to reproduce it, and what you think the impact is. Do not include real patient data.

We aim to acknowledge a report within three working days. This is a small team and a pre-release project, so we cannot promise a fix time, but we will tell you what we decide.

## What we consider in scope

- Authentication and authorisation: reading or changing another user's data, escalating to admin.
- Exposure of health data, tokens or secrets in logs, responses or the browser.
- Prompt injection that makes the chat give medicine advice, a dose, a diagnosis, or ignore its safety rules.
- Bypasses of the guard rails or the output check that let a refused request through.
- Injection (SQL, command, template), unsafe file upload, SSRF, or an unsafe default.
- Missing rate limits on sign-up, login or chat.

Out of scope: findings that need a modified client with a stolen token, volumetric denial of service, and the clinical content itself (report that as a normal issue; see [`docs/clinical-review.md`](./docs/clinical-review.md)).

## What is already in place

| Area | Control |
|---|---|
| Passwords | PBKDF2-HMAC-SHA256 with a random salt; never logged |
| Tokens | HMAC-signed JWT, 30-minute default life, issuer and audience checked, no profile or health data inside |
| Production start-up | Refuses the development JWT secret; `DEMO_MODE=false` removes the unauthenticated chat and demo routes |
| Input | Validation and length limits on every body; uploads checked by extension, type and size, hashed and reviewed before use |
| Rate limits | Separate limits for auth, chat, and the knowledge, sources, pregnancy, guidelines and Ayurveda routes, with a local fallback if Redis is down |
| Headers | CORS from an exact origin list; security headers on the API and the web app |
| Health data | Consent-gated, filtered by the signed-in user on every route, exportable and deletable ([`docs/privacy.md`](./docs/privacy.md)) |
| Retrieved text | Treated as data, never as instructions |
| Safety | Rule-based and independent of any model; fails closed |
| Logs | Request metadata and hashes, not questions, answers, tokens or health fields |
| Supply chain | `npm audit` and a secret scan (`backend/scripts/secret_scan.py`) in CI |

## Known gaps

- Branch protection on `main` is not enabled yet.
- The care, profile, privacy and resources routes have no rate limit (only auth, chat and the knowledge routes do).
- Chat history is removed with the account but not with the profile ([`docs/privacy.md`](./docs/privacy.md#a-gap-to-know-about)).
- There is no external penetration test, and no clinical or legal review.
- `RAG_ENGINE=external` sends the question and a short profile summary to a third-party provider; do not use it for real patients without an agreement with that provider.

## For deployers

Follow the production checklist in [`docs/deployment.md`](./docs/deployment.md): a unique `JWT_SECRET`, `ENVIRONMENT=production`, `DEBUG=false`, `DEMO_MODE=false`, exact `CORS_ORIGINS`, TLS, a managed database with encrypted backups, secrets in a secret manager, and `/admin`, `/evaluation` and `/internal/metrics` restricted at the network layer.
