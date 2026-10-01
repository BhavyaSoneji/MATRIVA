# Roadmap

What is left. Most of it needs people, not code. Issue numbers refer to the GitHub tracker.

## Before any real patient sees the app

| Item | Why it blocks | Needs | Issue |
|---|---|---|---|
| Clinician review of the care rules and the 1,231 guard rails | Thresholds, schedules and medicine rules are sourced but unreviewed | An obstetrician and a clinical pharmacist ([`clinical-review.md`](./clinical-review.md)) | #75, #82 |
| A `reviewed_by` and date on every rule, visible in the app | So "reviewed" is a fact, not a claim | Small code change after the first review | #82 |
| Native-speaker review of Hindi and Gujarati | Emergency wording must be right | One reviewer per language | #91 |
| Real review of the documents approved on instruction | The book and guidance were approved so answers could flow | A reviewer per document set | #88 |
| Legal review under the DPDP Act: retention, breach process, consent wording | Health data | A lawyer | #81 |
| Decide whether profile deletion should also delete chat history | Today only account deletion does ([`privacy.md`](./privacy.md#a-gap-to-know-about)) | A product decision, then a small change | |
| Confirm the Round 1 submission status | The Sep 25 date has passed | A team member | #68, #76 |
| Branch protection on `main` | Direct pushes are possible | A repository admin | #21 |

## Product

| Item | Why | Issue |
|---|---|---|
| Push or SMS reminders | Reminders show only while the app is open | #83 |
| Answers in Hindi and Gujarati | Today questions and refusals are, answers are English | #86 |
| A pilot: one clinic, 20 to 30 mothers, 8 weeks | Real use is the real test | #89 |
| A licence | None is chosen, so all rights are reserved | |

## Quality of the answers

| Item | Why | Issue |
|---|---|---|
| Paraphrases with no shared vocabulary still miss | "What if my baby kicks less" has no words in common with the source | #84 |
| An out-of-scope question can slip through on one shared rare word | The sufficiency gate is lexical | #85 |
| Damaged OCR pages cannot be quoted | Two-column scans merge | #87 |
| Verify each guard-rail rule against the exact page it cites | Sources are consistent references, not line-by-line checks | |
| Learn from false positives and misses | Add a way for users to report a wrong warning | |

## Engineering

| Item | Issue |
|---|---|
| CI step: a docs link check and `alembic upgrade head` on an empty database | #90 |
| Per-rule disable switch and an admin view of which rules fire | |
| Split `backend/app/data/guardrails/medications.yaml` (old grouped entries) into per-drug rules, then retire the grouped file | |

## Not planned

- Diagnosing, prescribing, dosing, or telling anyone to start, stop or change a medicine. This is a design rule, not a gap.
- A generative model writing medical text unreviewed. The default engine only quotes approved passages.
