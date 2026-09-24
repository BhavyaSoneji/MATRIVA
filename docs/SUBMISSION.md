# Health-a-thon 2026 — Round 1 Submission

**Track:** Maternal & Women's Health
**User:** Patient / Caregiver
**Use case:** Patient Education & Digital Engagement
**Repo:** https://github.com/BhavyaSoneji/MATRIVA

> Status: DRAFT. [TODO] markers below need a human pass before this is pasted into the official
> form — see the notes at the bottom of this file.

---

## Problem

Pregnant women navigating nutrition, lifestyle, and traditional-practice questions turn to generic
sources (search engines, social media, family advice) that blend modern medical evidence with
unverified traditional claims — without ever showing which is which, how strong the evidence is,
or when a symptom actually needs a doctor instead of a lifestyle answer. In India specifically,
this is compounded by real demand for Ayurvedic/traditional guidance (e.g. Garbhini Paricharya)
alongside modern antenatal care, with no tool that respects both without conflating them.

## Solution

MATRIVA is a source-grounded pregnancy education assistant. It never lets a language model be the
sole source of truth: every answer is retrieved from a curated, labelled knowledge base spanning
modern medical, Ayurvedic, nutrition, lifestyle, and regional/cultural domains, and is explicitly
separated into **modern medical guidance**, **traditional/Ayurvedic information**, and **uncertain
or limited evidence** before it reaches the user. A rule-based safety layer runs before generation
and can never be overridden by personalization — queries matching obstetric danger signs are
routed to a professional-care escalation message instead of an ordinary answer.

**Round 1 demo scenario:** a second-trimester patient asks a nutrition + Ayurveda question
("What should I eat, and are there Ayurvedic diet recommendations for this stage?"), receives a
cited, source-labelled answer, and sees her next antenatal-care visit from the FOGSI/WHO 8-contact
ANC schedule (weeks 12/20/26/30/34/36/38/40/41).

```
USER PROFILE → PREGNANCY CONTEXT → QUERY UNDERSTANDING → SAFETY PRE-CHECK →
KNOWLEDGE RETRIEVAL (RAG) → PERSONALIZATION → EVIDENCE FILTERING → SAFETY POST-CHECK →
LLM RESPONSE GENERATION → CITATIONS / SOURCES → USER-FACING RESPONSE
```

## Why it's trustworthy

- **Retrieval before generation, always.** The LLM (Groq) only ever answers from retrieved,
  labelled source material — it does not free-generate medical facts or invent citations.
- **Explicit evidence separation.** Every response distinguishes modern medical guidance from
  traditional/Ayurvedic content and flags uncertain evidence, rather than presenting all
  information with equal authority.
- **Independent, rule-based safety layer.** Safety is never delegated solely to the LLM. A
  pre-check keyword layer (obstetric danger signs — bleeding, severe headache/vision change,
  reduced fetal movement, severe abdominal pain, convulsions, fluid leak, high fever, severe
  swelling, persistent vomiting) short-circuits to a professional-care escalation message before
  the RAG/LLM pipeline runs at all. The system fails closed: if safety validation fails, the raw
  LLM response is never returned.
- **Sourced, not asserted.** Every knowledge entry carries `source`, `source_type`, and
  `evidence_level` metadata. Traditional/Ayurvedic content is explicitly labelled and requires
  clinical review sign-off before being presented as demo- or production-ready content — nothing
  is surfaced as verified until a qualified reviewer has checked it.
- **Grounded in established references and current safety-in-AI research:** FOGSI Good Clinical
  Practice Recommendations, the WHO 2016 antenatal-care model (8-contact schedule), Charaka
  Samhita (Sharirasthana, Garbhini Paricharya), and the broader academic literature on
  safety-constrained/grounded generation for medical LLM applications. [TODO: confirm and insert
  exact citations/DOI or arXiv links for the RAG-safety papers named in the brief — do not present
  unverified bibliographic details as confirmed].

## Feasibility in 60–90 days

The architecture is deliberately staged so a working (if narrow) system exists from day one and
widens in scope without rework:

| Phase | Scope | Status |
|---|---|---|
| Sprint 0 (Round 1, by Sep 25) | Hand-curated seed knowledge (FOGSI schedule, Garbhini Paricharya, IFCT foods), minimal keyword-retrieval + Groq generation, thin keyword-based safety pre-check, minimal `/chat` + visit-schedule endpoint, minimal chat UI | Backend/RAG/safety pieces complete; Clinical Lead sign-off ([#75](https://github.com/BhavyaSoneji/MATRIVA/issues/75)) and final demo assembly in progress |
| Sprint 1 (if shortlisted, Oct 5 – Nov 8) | Full ingestion pipeline (parsing, semantic chunking, metadata/quality checks), Gemini embeddings + pgvector, hybrid retrieval + reranking, full safety classifier (pre + post-check), citation validation, intent classification, retrieval/generation/safety evaluation harnesses | Scoped as 64 tracked GitHub issues across 3 milestones (see [`docs/FEATURES.md`](./FEATURES.md)) |
| Sprint 2+ | Personalization engine, recommendation engine, multi-domain query decomposition, admin/review tooling, deployment hardening | Scoped, not started |

We are not building a general-purpose medical chatbot or attempting diagnosis — scope is
intentionally narrow (education + safe escalation) so the 60–90 day window is spent on evidence
quality and safety correctness rather than breadth.

## Team

| Role | Name | Background |
|---|---|---|
| RAG / AI / Safety / Testing / Code Review | [@neevmodh](https://github.com/neevmodh) | — |
| Backend | [@BhavyaSoneji](https://github.com/BhavyaSoneji) | — |
| Frontend | [@Rajodedra](https://github.com/Rajodedra) | — |
| Clinical Lead | [TODO: name] | BAMS, MS-Gynaecology scholar — reviews all Ayurvedic/traditional content and the ANC visit schedule before anything ships (see [#75](https://github.com/BhavyaSoneji/MATRIVA/issues/75)) |

## Demo

[TODO: insert screenshots or a short screen recording of the working demo scenario once Bhavya's
`/chat` + visit-schedule endpoints ([#69](https://github.com/BhavyaSoneji/MATRIVA/issues/69)) and
Raj's chat UI ([#72](https://github.com/BhavyaSoneji/MATRIVA/issues/72)-[#74](https://github.com/BhavyaSoneji/MATRIVA/issues/74)) land.]

## Repository

https://github.com/BhavyaSoneji/MATRIVA

---

### Notes for whoever finalizes this (assigned: @neevmodh, blocking #76)

1. **[TODO] Clinical Lead name/credentials** — must come from the actual team member; do not
   invent this.
2. **[TODO] Academic RAG-safety citations** — the brief names MAM-AI, MamaBench, and
   safety-constrained LLM papers; I have not verified exact titles/authors/links for these and
   won't fabricate a citation, so confirm and paste the real references before submitting.
3. **[TODO] Screenshots/recording** — waiting on #69/#72-#74 per [`docs/WORKFLOW_NEEV.md`](./WORKFLOW_NEEV.md).
4. This doc assumes the Ayurveda/ANC-schedule content stays flagged pending review (per
   [`knowledge/seed/seed.yaml`](../knowledge/seed/seed.yaml)) unless #75 has actually closed by
   submission time — if it hasn't, say so plainly in the write-up rather than implying sign-off
   happened.
