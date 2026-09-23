# Frontend Workflow — Raj

Step-wise execution order for all frontend issues (`frontend` label, assignee `@Rajodedra`).
Work top to bottom. Don't start a step until its "Depends on" column is actually done — check
[`PROGRESS.md`](../PROGRESS.md) for real status before jumping ahead.

## Sprint 0 — Health-a-thon Round 1 (due Sep 25)

Do these first, in this order. Nothing below this section matters until Round 0 ships.

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 1 | [#72](https://github.com/BhavyaSoneji/MATRIVA/issues/72) Minimal chat UI | Input box, message list, source cards w/ evidence labels, calling `/chat` | Bhavya's #69 |
| 2 | [#73](https://github.com/BhavyaSoneji/MATRIVA/issues/73) "Next ANC visit" card | Small card calling `/pregnancy/next-visit` | Bhavya's #70 |
| 3 | [#74](https://github.com/BhavyaSoneji/MATRIVA/issues/74) Demo polish pass | Calm healthcare styling, no placeholder content, full click-through works | Steps 1-2 |

### Step 0 — minimal scaffold (prerequisite, not the full #41 build-out)

```bash
cd MATRIVA
npx create-next-app@latest frontend --typescript --tailwind --app --no-src-dir
cd frontend
npx shadcn@latest init
npx shadcn@latest add card input button
```

Just enough to run `npm run dev` — skip the full `components/hooks/types/styles` folder
structure from Section 6 for now; that's Sprint 1's job (step 4 below).

### Step 1 detail — #72 Minimal chat UI
1. One page (`app/page.tsx`): input box + message list.
2. On submit, `POST` to Bhavya's `/chat` endpoint with `{ message }`.
3. Render the response: answer text + a source card per citation, each showing an evidence-label
   badge (**Evidence reviewed** vs **Traditional source**) — the response shape is
   `{answer, sources[], evidence_label}`.
4. Visually separate modern-medical vs traditional/Ayurvedic content in the answer (two sections
   or two badge colors) — this is a judged differentiator, don't skip it.

### Step 2 detail — #73 "Next ANC visit" card
1. Small `<Card>` on the same page.
2. On page load, `GET` Bhavya's `/pregnancy/next-visit`.
3. Render "Your next visit: Week N" — frame the copy as personal encouragement, not a clinical
   instruction (e.g. "Your next check-up is coming up around week 26").

### Step 3 detail — #74 Demo polish pass
1. Apply calm healthcare tokens: soft green/blue neutral palette, generous whitespace, rounded
   cards, no harsh red except on an actual safety warning.
2. Remove all placeholder/lorem-ipsum text — every string visible on screen must be real demo
   content.
3. Final click-through: type the actual demo question end-to-end, confirm nothing errors, nothing
   is empty.

**Coordination point:** Steps 1-2 are blocked on Bhavya's `/chat` and `/pregnancy/next-visit`
endpoints (#69, #70) being live locally, and issue #71 wiring CORS. If Bhavya isn't ready yet,
build the UI against mocked JSON matching the expected response shape first, then swap the mock
for the real fetch call — don't sit idle waiting.

---

## Sprint 1 — Foundation (if shortlisted, build sprint Oct 5 - Nov 8)

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 4 | [#41](https://github.com/BhavyaSoneji/MATRIVA/issues/41) Full Next.js scaffold | Proper `app/components/lib/hooks/types/styles` structure per Section 6 (upgrades the Sprint 0 minimal scaffold) | — |
| 5 | [#42](https://github.com/BhavyaSoneji/MATRIVA/issues/42) Design system | Tailwind tokens: calm neutral/green/blue palette, typography, card surfaces, minimal icons, subtle animation rules | #41 |

## Sprint 1 — Auth & Onboarding

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 6 | [#43](https://github.com/BhavyaSoneji/MATRIVA/issues/43) Landing page | Positioning page, no fear-based UI | #42 |
| 7 | [#44](https://github.com/BhavyaSoneji/MATRIVA/issues/44) Sign up / login pages | Wired to backend `/auth/register`, `/auth/login`, JWT storage | #42, Bhavya's #27 |
| 8 | [#45](https://github.com/BhavyaSoneji/MATRIVA/issues/45) Onboarding flow | Multi-step profile/pregnancy/diet/region/consent form | #44, Bhavya's #28 |

## Sprint 1 — Core Experience

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 9 | [#46](https://github.com/BhavyaSoneji/MATRIVA/issues/46) Personalized dashboard | Stage, guidance categories, today's recs, saved recs, recent questions, safety notices | #45, Bhavya's #30/#31 |
| 10 | [#47](https://github.com/BhavyaSoneji/MATRIVA/issues/47) Full AI chat UI | Upgrades Sprint 0's #72: suggested questions, save-recommendation, feedback, domain labels | #46, #64 |
| 11 | [#64](https://github.com/BhavyaSoneji/MATRIVA/issues/64) Suggested questions & feedback UI | Split-out component wired to `POST /feedback` | Bhavya's #63 |

## Sprint 1 — Domain Pages

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 12 | [#48](https://github.com/BhavyaSoneji/MATRIVA/issues/48) Nutrition + lifestyle pages | Region/diet-filtered food & lifestyle content | Bhavya's #32, #59 |
| 13 | [#49](https://github.com/BhavyaSoneji/MATRIVA/issues/49) Ayurveda / traditional knowledge page | Provenance display (book/chapter/verse), evidence labels | Neev's #15, Bhavya's #33 |
| 14 | [#50](https://github.com/BhavyaSoneji/MATRIVA/issues/50) Stage-wise guidance page | Driven by pregnancy stage engine | Bhavya's #31 |
| 15 | [#51](https://github.com/BhavyaSoneji/MATRIVA/issues/51) Recommendations + saved items pages | Each rec shows its "why shown" reason | Bhavya's #30 |
| 16 | [#52](https://github.com/BhavyaSoneji/MATRIVA/issues/52) Sources / evidence explorer page | Browse cited sources by evidence status | Bhavya's #62 |
| 17 | [#53](https://github.com/BhavyaSoneji/MATRIVA/issues/53) Profile/settings + privacy/consent pages | Update/delete profile, data export, consent mgmt | Bhavya's #37 |

## Sprint 1 — Admin & Ops

| Step | Issue | Action | Depends on |
|---|---|---|---|
| 18 | [#54](https://github.com/BhavyaSoneji/MATRIVA/issues/54) Admin dashboard: document management UI | Upload -> review -> approve -> reindex flow | Bhavya's #34 |
| 19 | [#55](https://github.com/BhavyaSoneji/MATRIVA/issues/55) Evaluation dashboard | Visualize retrieval/generation/safety eval results | Bhavya's #36, Neev's #16-20 |
| 20 | [#56](https://github.com/BhavyaSoneji/MATRIVA/issues/56) Deploy frontend to production | Prod build, env vars, no exposed secrets | All above |
