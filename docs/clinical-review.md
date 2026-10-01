# Clinical review guide

Nothing in MATRIVA has been signed off by a clinician, a pharmacist or a native speaker. This page tells a reviewer **what to check, where it lives, and how to record the result**. It is the work behind issues #75, #82 and #91 and the last gate before any real patient sees the app.

## What needs reviewing, and by whom

| What | Where | Size | Reviewer |
|---|---|---|---|
| Visit schedule, supplement timing, reading flags, red-flag questions, nutrition targets | `backend/app/data/care_rules.yaml` | about 20 screening questions plus thresholds | Obstetrician or gynaecologist |
| **Medicine rules** | `backend/app/data/guardrails/medications.yaml`, `medicines_*.yaml`, `vaccines.yaml` | 918 rules | Clinical pharmacist, with an obstetrician |
| Herbs, foods, exposures | `herbs.yaml`, `foods.yaml`, `exposures.yaml`, `substances.yaml` | 205 rules | Obstetrician, dietitian; an Ayurvedic physician for `herbs.yaml` |
| Warning signs and request rules | `symptoms.yaml`, `requests.yaml` | 37 rules | Obstetrician |
| Rules tied to conditions | `condition_rules.yaml`, `watch.yaml` | 59 rules | Obstetrician; the relevant specialist for each condition |
| Output checks | `output.yaml` | 12 rules | Obstetrician, and a clinician who reads the replacement wording |
| Book regimen and avoid list | `backend/app/data/food_guide.yaml` | 37 entries | Ayurvedic physician and a dietitian |
| Seeded guidance paraphrases | `knowledge/seed/guidelines.yaml` | 26 entries | Obstetrician, against each `url` |
| **Hindi and Gujarati wording** | `messages.yaml`, `classes.yaml`, `requests.yaml`, `symptoms.yaml` (the `localized` and the Hindi and Gujarati terms) | all refusals, emergencies, and about 10,000 trigger phrases | Native speaker of each language, ideally a nurse or doctor |

## How the rules are built (so you know what you are reading)

- A medicine rule has a **class** that decides what MATRIVA says: `contraindicated` and `avoid` (refuse, with the reason), `doctor_only` and `otc_ask` (will not say whether to start, stop or change it), `supplement` (allowed as prescribed, with a warning against doubling up), `herbal` (treated as a medicine), `vaccine`.
- Every rule has `why` (the reason shown to the user) and `src` (keys into `sources.yaml`). **A key means "consistent with this reference", not "this page says exactly this".** That pairing is the first thing to verify.
- The default for anything uncertain is `doctor_only`, which asserts nothing about harm.
- `python -m app.safety.guardrails` (run in `backend/`) prints the counts. `python -m pytest tests/test_guardrails.py` checks the structure, not the clinical truth.

## A pharmacist's checklist for a medicine rule

1. **Is the class right?** Would you tell a pregnant patient to avoid it (`avoid`), never take it (`contraindicated`), or only take it under supervision (`doctor_only`)? A drug that is first line in pregnancy (for example labetalol, methyldopa, insulin, levothyroxine, low-dose aspirin, heparin, antiretrovirals, anti-TB drugs) must never read as "avoid".
2. **Is the reason (`why`) true and not alarmist?**
3. **Does the cited source actually support it?** Replace a root-page link with the exact page where you can.
4. **Are the brand and local names right?** A wrong alias only fires on text nobody types, but a missing common brand means the rule is missed.
5. **Does the message avoid advice?** It must never say a drug is safe, give a dose, or tell someone to stop.
6. **What does it do if the person says their doctor prescribed it?** `doctor_only` and `otc_ask` become a caution; `contraindicated` and `avoid` stay refusals that tell the person to call the prescriber today and not to stop other medicines.

## An obstetrician's checklist for a warning sign or request

- Is the action right: `escalate` (call 112 now), `block` (same-day review, no chat answer) or `caution`?
- Is the week gating right (`min_week`, `max_week`)? For example, reduced movements from week 20, regular contractions before and after 37 weeks.
- Do the numbers match the care rules and the helplines in [`data-sources.md`](./data-sources.md)?
- Are the legal statements right (MTP Act weeks, PCPNDT)?
- Is any wording alarmist or falsely reassuring? The output check also blocks "nothing to worry about".

## A native speaker's checklist

- Is each refusal and emergency message natural, polite and unambiguous at a glance? Would an ASHA read it out as written?
- Do the trigger phrases cover how people really say it, including Roman script (Hinglish) and common spellings? Add missing ones.
- Does any phrase mean something else in a common context and cause a false alarm?
- For Gujarati: the script and the vowel signs must be exact.

## Recording a review

There is no `reviewed_by` field yet, which is why issue #82 exists. Until then:

1. Review one file at a time and send corrections as a pull request: change the YAML, run the tests.
2. Record, in the pull request description, the reviewer's name, qualification, date and the file and commit reviewed.
3. Add a line to [`PROGRESS.md`](../PROGRESS.md) and tick the file off in the table above.

When every row has a named reviewer, change `review: pending_clinical_review` in `care_rules.yaml`, update the README's [honest limits](../README.md#-honest-limits), and only then consider a pilot (see [`care-features.md`](./care-features.md)).
