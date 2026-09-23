# Progress Log

Shared log for the team. **Add one entry every time you push a commit** (or finish a meaningful
chunk of work), newest entry at the top. Keep each entry short — a couple of lines is enough.

## How to add an entry

```
### YYYY-MM-DD — @your-github-handle
- What you did (1-3 bullets)
- Related issue(s): #<number>
- Status: in-progress / blocked / done
- Notes: anything the other two need to know (blockers, API changes, schema changes)
```

Paste your entry right below this line, above the older ones.

---

<!-- NEW ENTRIES GO HERE -->

### 2026-09-23 — @neevmodh
- Moved the Ayurveda source PDF (`Prasuti-Tantra-by-Dr-premvati-Tiwari.pdf`) into `knowledge/ayurveda/`
- Audited docs/FEATURES.md against the 56 existing issues and filed 8 more to close gaps:
  #57 intent classification, #58 multi-domain response segmentation, #59 lifestyle engine (backend),
  #60 security hardening, #61 knowledge search & sources API, #62 feedback API,
  #63 conversation memory (session vs profile), #64 suggested questions & feedback UI
- Added a Feature → Issue coverage map to docs/FEATURES.md so every feature traces to an issue number
- Related issue(s): #57-#64
- Status: done
- Notes: total backlog is now 64 issues across M1/M2/M3, all feature areas from FEATURES.md have
  at least one tracking issue.

### 2025-09-23 — @neevmodh
- Created docs/FEATURES.md (full functionality list) and this PROGRESS.md
- Filed 56 GitHub issues across 3 milestones (M1/M2/M3), labeled and assigned per workstream
  (rag-ai/testing/review → @neevmodh, backend → @BhavyaSoneji, frontend → @Rajodedra)
- Added `.github/CODEOWNERS`
- Related issue(s): #21 (workflow setup)
- Status: done
- Notes: Backend uses Groq (generation) + Gemini (embeddings). Everyone: update this file after
  every commit so we always know real project status without digging through git log.
