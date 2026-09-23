# Feature List — Holistic AI Pregnancy Guidance Platform

Full functionality scope derived from `Master Prompt.txt`. Each section maps to GitHub issues
(labels: `rag-ai`, `backend`, `frontend`, `testing`, `review`) tracked across milestones
`M1: Foundation + RAG Core`, `M2: Personalization + Safety + Domain Engines`,
`M3: Frontend + Admin + Evaluation + Deploy`.

## 1. User & Account
- Sign up / login (JWT auth)
- Structured onboarding (profile, pregnancy, health, lifestyle, culture)
- Consent capture for data storage
- Profile update / delete
- Data export & account deletion (privacy)

## 2. Pregnancy Profile & Personalization
- Pregnancy profile (week, trimester, stage, due date, first pregnancy y/n)
- Deterministic pregnancy-stage engine
- Health context (known conditions, doctor restrictions, dietary/activity restrictions)
- Lifestyle profile (activity level, occupation, sleep, stress)
- Cultural/dietary profile (region, food culture, language, traditional practice preference)
- Personalization engine (selects relevant info using stage+diet+region+restrictions — never invents medical facts)

## 3. AI Assistant / Conversational AI
- Chat interface (`/chat`) with conversation history
- Query understanding / intent classification (NUTRITION, EXERCISE, LIFESTYLE, MENTAL_WELLBEING,
  ANTENATAL_CARE, PREGNANCY_DEVELOPMENT, AYURVEDA, TRADITIONAL_PRACTICE, FOOD, MEDICAL_CONCERN,
  MEDICATION, EMERGENCY, GENERAL, OTHER)
- Multi-domain query handling (splits answer into modern medical vs traditional vs evidence status)
- Session vs. permanent-profile memory separation
- Suggested questions, feedback on responses

## 4. Knowledge & RAG Pipeline
- Multi-domain knowledge base: Modern Medical, Ayurveda, Nutrition, Lifestyle, Regional/Cultural
- Document ingestion pipeline (parse → clean → structural analysis → chunk → metadata enrichment →
  quality check → embed → index)
- Semantic chunking (300–700 tokens, structure-preserving)
- Duplicate detection (hash + semantic similarity)
- Embedding pipeline (Gemini) + pgvector storage, with re-indexing on document change
- Hybrid retrieval (vector search + metadata filters + keyword search)
- Reranking (relevance, stage, evidence level, region, source quality)
- Context packet construction for the LLM
- LLM response generation (Groq), source-grounded system prompt
- Citation validation (no fabricated sources/pages/URLs)
- "Insufficient evidence" fallback instead of hallucination

## 5. Evidence & Source Attribution
- Every knowledge document carries: source, source_type, evidence_level, review_status, reviewer info
- Ayurveda-specific provenance: book, chapter, verse/page, original text, translation, interpretation
- Evidence labels: TRADITIONAL, PRELIMINARY, LIMITED_EVIDENCE, MIXED_EVIDENCE, SUPPORTED, UNCERTAIN,
  NOT_ESTABLISHED
- Source cards / evidence explorer UI showing source, topic, evidence status, relevance
- Clear separation of modern-medical vs traditional/Ayurvedic content in responses

## 6. Safety Layer (independent of the LLM)
- Safety pre-check classifier (routes query before generation)
- Risk categories: SAFE_GENERAL, LOW_CONCERN, MEDICAL_REVIEW, HIGH_RISK, URGENT_ESCALATION,
  INSUFFICIENT_INFORMATION
- Safety post-check validator: unsupported-claim detection, dangerous-recommendation detection,
  missing-escalation detection, source-consistency check, evidence-mismatch check
- Emergency escalation routing (no diagnosis, no false reassurance, directs to professional care)
- Prompt-injection defense (retrieved text treated strictly as data, never instructions)
- Fail-closed behavior if the safety subsystem itself fails

## 7. Recommendation Engine
- Rule + retrieval based (not ML) recommendation flow: profile → stage → intent → retrieval →
  eligibility filter → safety filter → ranking
- Every recommendation stores reason, source documents, evidence level, domain, safety status
- "Why was this recommended?" explanation shown to user
- Save / view saved recommendations

## 8. Food & Regional Engine
- Structured food database (name, local names, region, cuisine, ingredients, dietary type, season,
  nutrition metadata, cultural relevance, pregnancy context, evidence status, sources)
- Dietary/region-based filtering
- Explicit separation of "traditional" from "safe" (never auto-equated)

## 9. Lifestyle Engine
- Activity, sleep, work, travel, relaxation, yoga, meditation, daily routine guidance
- Every activity recommendation filtered through user restrictions + safety rules + evidence

## 10. Admin / Knowledge Management
- Document upload, view, domain/stage/source-type/evidence-level assignment
- Document review → approve/reject workflow (nothing goes live unreviewed)
- Re-index documents; view chunking & embedding status
- Manage safety rules
- View evaluation results

## 11. Evaluation & Testing
- Retrieval evaluation (Recall@K, Precision@K, MRR, nDCG)
- Generation evaluation (relevance, groundedness, citation correctness, completeness, clarity)
- Safety evaluation (synthetic red-flag/emergency/medication test cases)
- Hallucination testing (out-of-corpus questions)
- Full 12-case test matrix (general, stage-specific, dietary, regional, Ayurvedic, multi-domain,
  unknown, medical concern, urgent, prompt injection, source contradiction, empty retrieval)
- Evaluation dashboard (UI)

## 12. Frontend Pages (17 total)
Landing · Sign up/login · Onboarding · Dashboard · AI chat · Nutrition · Lifestyle ·
Ayurveda/traditional knowledge · Stage-wise guidance · Recommendations · Saved items ·
Sources/evidence explorer · Profile/settings · Privacy/consent · Admin dashboard ·
Knowledge management · Evaluation dashboard

## 13. Platform / Cross-cutting
- REST API (auth, profile, pregnancy, chat, recommendations, knowledge search, sources, feedback,
  admin, evaluation endpoints)
- Security: authN/authZ, input validation, rate limiting, secure password storage, HTTPS, env
  secrets, audit logs
- Privacy: minimal data collection, consent, deletion, export, no unnecessary health-data logging
- Observability: latency, retrieval count, safety classification, error rate, token usage tracking
- Error handling with graceful degradation for every external dependency (LLM, DB, vector DB,
  embeddings)

## Ownership (see `.github/CODEOWNERS`)
| Area | Owner |
|---|---|
| RAG / Safety / LLM / Evidence / Ingestion / Evaluation / Testing / Review | @neevmodh |
| Backend (API, DB, services) | @BhavyaSoneji |
| Frontend (Next.js UI) | @Rajodedra |
