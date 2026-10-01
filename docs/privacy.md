# Privacy

What MATRIVA stores about a person, where, for how long, and how to take it back. This describes the software as built. It is an engineering description, not a legal opinion: a legal review under the DPDP Act, 2023 is still open (issue #81).

## What is stored

| Data | Table | Stored when | Consent needed |
|---|---|---|---|
| Account: email, password hash (PBKDF2-HMAC-SHA256, random salt), name | `users` | Sign-up | No (needed to have an account) |
| Consent record and version | `consent_records` | Onboarding, Settings | It *is* the consent |
| Pregnancy week and due date | `pregnancy_profiles`, `pregnancy_dating` | You enter them | Yes |
| Conditions, **current medicines**, allergies, risk factors, age, blood group, restrictions | `health_profiles` | You enter them in Settings | Yes |
| Lifestyle, diet, region, language | `lifestyle_profiles`, `dietary_profiles`, `cultural_profiles` | You enter them | Yes |
| Daily check-ins | `daily_checkins` | You submit one | Yes |
| Readings (Hb, BP, weight, sugar) | `health_readings` | You add one, or say "my Hb is 9.8" in chat | Yes |
| Meals | `meal_logs` | You log one, or say "I ate 2 roti" in chat | Yes |
| Safety-check results | `screening_records` | You run `/check` | Yes |
| Emergency contact | `emergency_contacts` | You enter it | Yes |
| Daily water, sleep, activity | `daily_wellness_logs` | You log them | Yes |
| **Chat history**: your questions and the answers, with intent and safety status | `conversations`, `messages` | Every chat | No |
| Recommendations you saved, feedback you gave | `recommendations`, `feedback` | You tap them | No |
| Safety events: a **hash** of the question, the risk level, which rules matched | `safety_events` | A question matched a safety rule | No |
| Audit entries: export, delete, consent changes, admin actions | `audit_logs` | The action | No |

Questions are never written as readings or meals. Only plain statements are ("my Hb is 9.8"), only with consent, and only when the question was not an emergency.

## What is not stored or sent

- **Passwords and tokens** are never logged. Passwords are one-way hashes. Tokens carry no profile or health data.
- **Request logs** hold route, status, timing and a request id, not your text or your health fields. Safety events hold a hash of the question, not the question.
- **Your safety profile never leaves the backend.** The guard rails read your conditions, medicines, allergies, age and blood group inside the process. They are not sent to an AI model.
- **In the default engine nothing is sent anywhere.** In `RAG_ENGINE=external`, the question and a short profile summary (week, diet, region, conditions, allergies; never your name or contacts) are sent to the model provider you configured. Do not use that mode for real patients without a data-processing agreement with that provider.

## Your controls

| You want to | Do this | What happens |
|---|---|---|
| See everything | Settings, **Export my data** (`GET /privacy/export`) | JSON with your account, profile, care data, pregnancy, conversations, saved items, feedback and consent history |
| Stop sharing health data | Settings, **Withdraw consent** (`POST /privacy/consent` with `granted: false`) | Profile and health data are deleted |
| Remove your health profile | `DELETE /profile` | Profile, pregnancy, consent records and all care data (check-ins, readings, meals, dating, contact, screening, wellness) are deleted |
| Delete everything | Settings, **Delete my account** (`DELETE /privacy/account`) | The account and everything linked to it, **including chat history**, is deleted |

### A gap to know about

Withdrawing consent and deleting the profile remove health and care data, **but chat history stays until the account is deleted.** A message can contain health details the person typed. If that matters for your deployment, delete the account, or add conversation deletion to the profile delete. This is tracked in [`roadmap.md`](./roadmap.md).

## Who can see what

- You see your own data. Nobody else can read your conversations or care data through the API: every route filters by the signed-in user.
- Administrators manage documents, safety rules and evaluations. Their actions are audited. Protect `/admin`, `/evaluation` and `/internal/metrics` at the network layer as well.
- Developers with database access can read everything. Restrict and encrypt it ([`deployment.md`](./deployment.md)).

## Minimisation

Everything about health is optional and consent-gated, and the app works without any of it. The safety profile is there to make warnings personal; leave it empty and the guard rails still run on the words alone.
