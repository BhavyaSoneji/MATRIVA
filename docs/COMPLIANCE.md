# Government Guidance & Policy Alignment

MATRIVA gives maternal-health guidance in India, blends modern medical and Ayurvedic content, and
handles sensitive personal health data — so it sits inside several regulatory and clinical-guidance
frameworks even as an education-only (non-diagnostic) tool. This doc lists what the project must
align with, and what that means concretely for the codebase.

**Everything below needs sign-off from the Clinical Lead (see [#75](https://github.com/BhavyaSoneji/MATRIVA/issues/75))
and, before public launch, a legal reviewer. Do not present this file as a compliance certification —
it is an engineering checklist of frameworks to align with, not a legal opinion.**

---

## 1. Maternal-health program guidance (content grounding)

Modern-medical content, ANC scheduling, and risk-escalation thresholds should trace back to these
sources rather than being generated freeform:

| Source | Relevance |
|---|---|
| **MoHFW — Guidelines for Antenatal Care and Skilled Attendance at Birth** | Baseline ANC content and danger-sign list |
| **Pradhan Mantri Surakshit Matritva Abhiyan (PMSMA)** | Fixed-day (9th of every month) free ANC guarantee — reference when surfacing ANC visit reminders |
| **Janani Suraksha Yojana (JSY)** / **Janani Shishu Suraksha Karyakram (JSSK)** | Safe-delivery and free-entitlement schemes — relevant if the product ever signposts government benefits |
| **POSHAN Abhiyaan / POSHAN 2.0** (Ministry of Women & Child Development) | National maternal & child nutrition guidance — cross-check nutrition content against this, not just IFCT tables |
| **RMNCH+A strategy / National Health Mission** | Overall maternal-child health framework the ANC schedule and risk categories should stay consistent with |
| **WHO 2016 ANC model** (already cited in `docs/SUBMISSION.md`) | Already in use for the 8-contact schedule |
| **FOGSI Good Clinical Practice Recommendations** (already cited) | Already in use for the safety pre-check danger-sign list |

**Action:** `backend/app/safety/pre_check.py`'s danger-sign list and any future ANC-schedule code
should cite which of these documents each rule/date came from, the same way `knowledge/seed/seed.yaml`
already tracks `source` per entry.

## 2. Traditional / Ayurvedic content governance

| Source | Relevance |
|---|---|
| **Ministry of AYUSH** | Governing body for Ayurveda-related public guidance in India; any Ayurveda content presented as "AYUSH-aligned" should actually be checked against Ministry of AYUSH published material, not assumed |
| **National Commission for Indian System of Medicine (NCISM)** | Standards body for Ayurvedic practice — relevant if the project ever claims professional-standard equivalence |
| **Drugs and Magic Remedies (Objectionable Advertisements) Act, 1954** | Prohibits claiming a treatment/remedy cures/prevents specific conditions without basis — directly relevant to how Ayurvedic/traditional content is phrased. Evidence labels (`TRADITIONAL`, `PRELIMINARY`, etc.) already required by `docs/FEATURES.md` §5 exist partly for this reason; wording in generated answers must never imply a cure or guaranteed outcome |

**Action:** the existing rule ("traditional is never auto-equated with safe/effective," `docs/FEATURES.md`
§8) is the right posture — keep it, and make sure the LLM system prompt (`backend/app/llm`) explicitly
forbids therapeutic-claim language for traditional content.

## 3. Data protection & privacy

| Source | Relevance |
|---|---|
| **Digital Personal Data Protection Act (DPDP), 2023** | Governs collection/storage/processing of personal data in India, including health data collected at onboarding (pregnancy status, health conditions). Requires: purpose limitation, consent, data minimization, breach notification, and a user's right to access/correction/erasure |
| **IT Act, 2000 + IT (Reasonable Security Practices) Rules, 2011** | "Sensitive personal data" (health data falls under this) requires documented security practices and consent before collection |

**Action:** `docs/FEATURES.md` §1 and §13 already list consent capture, data export, and account
deletion as features — under DPDP these aren't optional nice-to-haves, they're the legal basis for
collecting pregnancy/health data at all. Recommend pulling consent capture + deletion into MVP scope
rather than deferring both to post-MVP (currently listed as deferred in the MVP/Features split — worth
revisiting: consent-at-collection specifically should move into MVP; export/delete can stay deferred
for a Round-1/demo build but must land before any real user data is collected).

## 4. Digital health / AI governance

| Source | Relevance |
|---|---|
| **Ayushman Bharat Digital Mission (ABDM)** | India's digital health interoperability framework. Not required for MVP, but if MATRIVA ever exchanges health records or integrates with providers, ABDM standards (health IDs, consent managers) apply |
| **NITI Aayog — Responsible AI for All / AI principles** | General guidance on safety, transparency, accountability for AI systems used in sensitive domains — aligns with the project's existing "independent safety layer, fail-closed" design |
| **MeitY advisories on AI-generated content (2024–)** | Recommend disclosing that responses are AI-generated and evidence-graded, not authored by a clinician — should be visible in the chat UI, not just in a README |

**Action:** the frontend chat UI should carry a persistent, visible disclosure ("AI-generated,
educational only, not medical advice") — this is currently implied by the README's framing but not
confirmed as a UI requirement in `docs/FEATURES.md` §12. Recommend adding it explicitly.

## 5. Scope boundary: this is not telemedicine

| Source | Relevance |
|---|---|
| **Telemedicine Practice Guidelines, 2020 (National Medical Commission)** | Governs remote consultation, prescription, and diagnosis by registered practitioners. MATRIVA does **not** diagnose, prescribe, or replace a consultation — this boundary must stay explicit everywhere: onboarding copy, chat disclaimers, and the emergency-escalation message |

**Action:** no code change needed if the existing "no diagnosis, no false reassurance, escalate to
professional care" rule (`docs/FEATURES.md` §6, already implemented in `pre_check.py`) is enforced
consistently — but this is the boundary that keeps the product outside telemedicine regulation, so it
should never be relaxed for UX reasons (e.g. never let generation "sound like" a prescription).

---

## Open items before any real-user launch (not just Round 1 demo)

1. Legal review of DPDP Act obligations for health-data collection — consent flow, retention policy,
   breach process.
2. Clinical Lead sign-off (#75) confirming ANC schedule and Garbhini Paricharya content against the
   primary MoHFW/FOGSI/Charaka Samhita sources, not secondhand summaries.
3. Confirm no wording in LLM-generated Ayurvedic content could be read as a therapeutic claim under
   the Drugs and Magic Remedies Act.
4. Add a persistent AI-disclosure element to the chat UI.
5. Decide (with legal input) whether consent-at-signup needs to move from "deferred" into MVP scope
   given DPDP applies from first data collection, not from a later "privacy features" milestone.
