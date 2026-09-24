# Safety layer

Safety is independent of the LLM and runs before and after generation.

## Pre-check

The classifier normalizes input and routes configured emergency, high-risk, medication, and
medical-review patterns. A match short-circuits normal generation and returns a professional
care/emergency escalation message. Safety rules are stored in `safety_rules`, versioned,
reviewed, and manageable by administrators.

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
