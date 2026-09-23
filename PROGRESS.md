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
- URGENT — Health-a-thon 2026 Round 1 is due **Sep 25** (not the full MVP, but written solution
  concept + methodology; real MVP is Nov 8 after shortlist). Track = Maternal & Women's Health,
  User = Patient/Caregiver, Use case = Patient Education & Digital Engagement.
- Opened milestone `R0: Round 1 Submission` and filed 12 issues (#65-#76, label `sprint-0`) split
  3 ways: seed knowledge + minimal RAG script + safety pre-check + submission doc (me), minimal
  /chat + ANC visit-schedule endpoints (Bhavya), minimal chat UI + visit card + demo polish (Raj)
- Full plan saved at the roadmap doc referenced in this conversation — single demo scenario: 2nd
  trimester patient asks a nutrition+Ayurveda question, gets a cited answer, sees her next ANC
  visit from the FOGSI 8-contact schedule
- Related issue(s): #65-#76
- Status: in-progress
- Notes: **Everyone drop other work and prioritize their R0 issues until Sep 25.** M1/M2/M3
  backlog resumes only if shortlisted (Oct 3). Clinical Lead (BAMS/MS-Gynaec) must sign off on the
  Garbhini Paricharya verses and ANC schedule before they go in the demo or write-up (#R0 checkpoint
  issue). Exact submission form/platform not yet confirmed — check healthathon.reskilll.com.

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
