# Care features

Endpoints are listed in [`api.md`](./api.md#care-features-care-authenticated); the safety side is in [`safety.md`](./safety.md).

What MATRIVA asks for, how a mother uses it, and what she gets back. All of it is reachable from the chat (slash commands or the sidebar); there are no extra pages.

| Command | Input | What she gets |
|---|---|---|
| `/plan` | Last period date, due date, or current week (set in onboarding/Settings) | Exact week and day, due date, visit calendar (FOGSI weeks, PMSMA on the 9th), iron-folic-acid course from week 16, this week's tasks |
| `/checkin` | Mood, symptoms, baby movement, iron tablet taken (under 20 seconds) | Streaks, reminders, and an immediate triage card if an answer is a warning sign |
| `/check` | Yes/no questions filtered by week | Emergency / urgent / soon outcome with one-tap 112, her emergency contact, and a hospital map link |
| `/readings` | Hb, BP, weight, sugar by hand, pasted report text, or a photo (needs `tesseract` on the server) | Trend chart and sourced flags (WHO Hb < 11; BP 140/90 and 160/110). Parsed values are shown for confirmation before saving |
| `/meals` | Free text: "2 roti, 1 katori dal, curd" | Approximate nutrients vs a pregnancy day, and vegetarian/allergy-aware foods to close gaps |
| `/summary` | None (built from the above) | One printable page for the doctor, with questions she may want to ask |
| `/book` | A term, e.g. *stanya* | The Prasuti Tantra by chapter, authorities cited, bilingual glossary |
| `/map` | The last question asked | How the topics in the answer connect |

Saying "my Hb is 9.8" or "I ate 2 roti and dal" in plain chat records it too (requires consent; questions are never recorded).

## Limits to know
- Thresholds and screening rules are sourced, but marked `pending_clinical_review` in `backend/app/data/care_rules.yaml`. A clinician must review them before real use.
- Nutrient numbers come from USDA per-100g data and everyday portions; they are estimates.
- Reminders show only while the app is open; there is no push or SMS channel yet.
- Health data is consent-gated; revoking consent, deleting the profile or the account purges it, and `/privacy/export` includes it.
- The Hindi/Gujarati red-flag phrases need native-speaker review.

## Suggested pilot
Run with one clinic for 20-30 mothers for 8 weeks; ask the doctor to review the rules file first, and measure check-in streaks, visits kept and flags raised.
