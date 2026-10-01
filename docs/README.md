# Documentation

Everything about MATRIVA, in one place. If you are new, read the [project README](../README.md) first, then follow the path for your role.

## By role

| You are | Read, in this order |
|---|---|
| **A mother, ANM, ASHA or doctor** | [Care features](./care-features.md) · [What to eat](./food-guide.md) · [Privacy](./privacy.md) · [FAQ](./faq.md) |
| **A clinician, pharmacist or native-speaker reviewer** | [Clinical review guide](./clinical-review.md) · [Guard rails](./guardrails.md) · [Data sources](./data-sources.md) · [Glossary](./glossary.md) |
| **A developer** | [Architecture](./architecture.md) · [API](./api.md) · [Configuration](./configuration.md) · [Testing](./testing.md) · [Contributing](../CONTRIBUTING.md) |
| **Working on retrieval** | [RAG](./rag.md) · [Offline RAG engine](./local-rag.md) |
| **Deploying it** | [Deployment](./deployment.md) · [Configuration](./configuration.md) · [Security](../SECURITY.md) |
| **A reviewer of the project** | [Tech blog](./TECH_BLOG.md) · [Compliance](./COMPLIANCE.md) · [Roadmap](./roadmap.md) · [Submission](./SUBMISSION.md) |

## All pages

| Page | What it covers |
|---|---|
| [`architecture.md`](./architecture.md) | Modules, request flow, data model, trust boundaries |
| [`api.md`](./api.md) | Every endpoint, the chat stream format, errors |
| [`care-features.md`](./care-features.md) | The slash commands, what each needs and returns, the safety profile |
| [`food-guide.md`](./food-guide.md) | The book's month-wise regimen and nutrient food lists |
| [`guardrails.md`](./guardrails.md) | The 1,231 safety rules, how a question is checked, limits |
| [`safety.md`](./safety.md) | The whole safety model: pre-check, guard rails, retrieval gate, output check, privacy controls |
| [`clinical-review.md`](./clinical-review.md) | What a reviewer must check, with checklists |
| [`privacy.md`](./privacy.md) | The data map and your controls |
| [`COMPLIANCE.md`](./COMPLIANCE.md) | Indian policy and law the project aligns with |
| [`rag.md`](./rag.md) · [`local-rag.md`](./local-rag.md) | The retrieval pipeline, schema, offline engine and measured results |
| [`configuration.md`](./configuration.md) | Every environment variable |
| [`deployment.md`](./deployment.md) | Docker, production checklist, health and observability |
| [`testing.md`](./testing.md) | The suites, what each proves, how retrieval is measured |
| [`data-sources.md`](./data-sources.md) | Every source behind the knowledge base and the rules |
| [`glossary.md`](./glossary.md) | Ayurvedic, clinical and software terms |
| [`faq.md`](./faq.md) | Short answers to common questions |
| [`roadmap.md`](./roadmap.md) | What is left |
| [`FEATURES.md`](./FEATURES.md) | The original scope and what has grown since |
| [`TECH_BLOG.md`](./TECH_BLOG.md) | How and why it was built, including what failed |
| [`SUBMISSION.md`](./SUBMISSION.md) | The Round 1 write-up |
| [`WORKFLOW_*.md`](./WORKFLOW_NEEV.md) | The original sprint plans (historical) |

## Keeping the docs true

Numbers in the docs come from the code: run `python -m app.safety.guardrails` in `backend/` for the rule counts, and the test commands in [`testing.md`](./testing.md) for the test counts. When you change behaviour, change the page that describes it in the same pull request, and add an entry to [`../PROGRESS.md`](../PROGRESS.md).
