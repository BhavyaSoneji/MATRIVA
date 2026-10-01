# Safety layer

Safety is independent of the LLM and runs before and after generation.

## Pre-check

The classifier normalizes input and routes configured emergency, high-risk, medication, and
medical-review patterns. A match short-circuits normal generation and returns a professional
care/emergency escalation message. Safety rules are stored in `safety_rules`, versioned,
reviewed, and manageable by administrators.

The pre-check understands English, Hindi, Hinglish and Gujarati red-flag phrases. The Hindi and
Gujarati wording still needs native-speaker review.

## Structured screening

Separately from chat, `/care/screening` asks about 20 yes/no questions filtered by the week of
pregnancy and returns an **emergency / urgent / soon** outcome with the source of each question
(WHO, FOGSI, NHS), one-tap 112, the mother's emergency contact and a hospital map link. A daily
check-in answer that is a danger sign triggers the same card. Reading thresholds (Hb < 11 g/dL,
BP 140/90 and 160/110) are applied by rules, never by a model. All of it is in
`backend/app/data/care_rules.yaml`, marked `pending_clinical_review`.

## Post-check

Generated text is rejected or replaced when it:

- contains a dangerous treatment/medication instruction;
- omits escalation for a high-risk query;
- cites a source that was not retrieved; or
- has no approved source for a grounded answer.

The system fails closed if the safety subsystem, retrieval dependency, or required source
set is unavailable. A `503` response is intentional and must not be replaced with a guessed
answer.

## Privacy and abuse controls

- Explicit consent is required before profile/pregnancy data is stored.
- Consent withdrawal deletes the associated profile data.
- Account export and deletion are available to the account owner.
- Chat session context is separate from permanent profile records.
- Raw health text, passwords, JWTs, and generated answers are excluded from normal logs.
- Rate limits apply to auth, chat, and public knowledge routes.
- Uploads are extension/MIME/size checked, hashed, reviewed, and indexed before activation.
- Audit records cover document decisions, safety-rule changes, exports, deletions, and consent.

Clinical thresholds and wording require qualified medical review. Engineering tests cannot
certify clinical correctness or replace a clinical governance process.
