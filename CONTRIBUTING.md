# Contributing to MATRIVA

Thank you for helping. This is a health product, so the bar is: **say what you can source, refuse what you cannot, and never advise on a medicine.** Please read the [README](./README.md) and [`docs/guardrails.md`](./docs/guardrails.md) before changing anything that answers a user.

## Set up

```bash
git clone https://github.com/BhavyaSoneji/MATRIVA && cd MATRIVA
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp ../.env.example .env              # set JWT_SECRET to 32+ random characters
alembic upgrade head
pytest -q                            # 513 tests should pass
cd ../frontend && npm install && npm run dev
```

No API key is needed. See [`docs/configuration.md`](./docs/configuration.md) for every setting.

## Where things live

| Change | Look in |
|---|---|
| A medicine, herb, food or warning sign the chat should handle | `backend/app/data/guardrails/*.yaml` |
| A threshold, visit week or screening question | `backend/app/data/care_rules.yaml` |
| The book's regimen or the nutrient list | `backend/app/data/food_guide.yaml` |
| An API route | `backend/app/api/` and `backend/app/services/` |
| A card in the chat | `frontend/components/` and `frontend/components/care/` |
| Retrieval | `backend/app/rag/local/` |
| Ownership | [`.github/CODEOWNERS`](./.github/CODEOWNERS) (the last matching rule wins) |

## Add or change a guard rail

Rules are data. A new medicine is one line:

```yaml
- cls: doctor_only                      # contraindicated | avoid | doctor_only | otc_ask | herbal | supplement | vaccine
  why: "antibiotics are only for infections your doctor has diagnosed"
  src: [nhs-medicines, acog]            # keys in sources.yaml; an unknown key fails the tests
  items: ["cefaclor|distaclor"]         # generic name | brand | brand
```

Rules of thumb:

1. **Use a class that asserts only what you can support.** If you are unsure, use `doctor_only`: it says nothing about harm.
2. **Never write a message that says a medicine is safe, gives a dose, or tells someone to stop.** The output check and the tests will also catch it.
3. **Cite where you can.** Link the exact page; a root-page link is a last resort. A key means "consistent with this reference", so say that honestly.
4. **Do not add a trigger that is an everyday word.** "Tea", "salt", "travel" and "show" would put a warning on ordinary questions. `tests/test_guardrails.py` runs every benchmark question through the rules and fails if one is blocked.
5. **Add Hindi and Gujarati** for anything that escalates, and mark it for native-speaker review.
6. Run `cd backend && python -m app.safety.guardrails` to see the new counts, and update any number you changed in the docs.

## Before you open a pull request

```bash
cd backend && pytest -q && ruff check . && mypy app/
cd ../ingestion && pytest tests/
cd ../evaluation && pytest tests/
cd ../frontend && npm run lint && npm run typecheck && npm run build && npx playwright test
```

Stop any server already listening on port 3000 first, or Playwright will reuse it and test old code. CI runs the same checks.

Your pull request should:

- do one thing, with tests for what it changes;
- change the docs that describe it, in the same pull request;
- add an entry to [`PROGRESS.md`](./PROGRESS.md) (newest first: what you did, related issue, status, notes);
- never include a secret, a real person's data, or a medical claim you cannot source.

## Medical content needs a reviewer

Changes to thresholds, medicine rules, warning signs, Hindi or Gujarati wording, or the book's regimen change what a patient is told. Ask for a review from a clinician, pharmacist or native speaker, and say so in the pull request. [`docs/clinical-review.md`](./docs/clinical-review.md) has the checklists.

## Commit messages

Short imperative subject saying what changed and why it matters ("Refuse home abortion questions and explain the MTP Act"), then a body when the reason is not obvious.
