## What and why

<!-- One or two sentences. Link the issue. -->

## Checklist

- [ ] Tests added or updated, and they pass: `cd backend && pytest -q`, `cd frontend && npx playwright test` (stop any server on port 3000 first)
- [ ] `ruff check`, `mypy app/`, `npm run lint`, `npm run typecheck` are clean for the files I changed
- [ ] The docs that describe this change are updated in this pull request, and any number I changed (rule counts, test counts) comes from the code (`python -m app.safety.guardrails`)
- [ ] I added an entry to `PROGRESS.md`
- [ ] No secret, no real person's data, and no medical claim I cannot source

## Safety review

Tick the ones that apply. Each needs a reviewer who is not the author.

- [ ] Changes what a patient is told (a rule, a threshold, a message, the book's regimen). A clinician, pharmacist or native speaker has been asked to review: see `docs/clinical-review.md`
- [ ] Adds or changes a guard-rail rule. It uses a class that asserts only what I can support, cites a source, has Hindi and Gujarati if it escalates, and `tests/test_guardrails.py` passes (including the benchmark questions that must not be blocked)
- [ ] Touches health data, consent, export or deletion. `docs/privacy.md` is updated
- [ ] Changes a database model. The migration checks what exists first and `tests/test_migrations.py` passes

## Not in this pull request

<!-- Anything you deliberately left out, so the reviewer does not look for it. -->
