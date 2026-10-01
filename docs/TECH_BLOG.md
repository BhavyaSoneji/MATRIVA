# Building MATRIVA: a pregnancy companion that has to be right, or say it can't

*A tech blog on the design decisions, the dead ends and the numbers.*

![The companion](screenshots/11-chat-answer.jpg)

## 1. The problem

A pregnant woman in India asks a question — *can I eat papaya? is this headache normal? what does Ayurveda say about the third month?* — and gets answers that blend modern guidelines with unverified tradition, with no sign of which is which, how strong the evidence is, or when to stop reading and call a doctor.

Two failure modes matter more than any feature:

1. **A confident wrong answer** (a hallucinated dosage, an invented rule).
2. **A missed emergency** (bleeding, severe headache with swelling, reduced movements) treated as an ordinary wellness question.

Everything below follows from taking those two seriously.

## 2. One window, not twenty pages

The first version had a page for everything: dashboard, nutrition, Ayurveda, sources, recommendations. It was messy and nobody knew where to start. We collapsed it into a **single chat workspace**. Features became slash commands and inline cards: `/plan`, `/readings`, `/meals`, `/book`. Old URLs redirect into the chat. A new user has one place to look and one verb: *ask*.

The inline-card idea turned out to be the most useful UI decision. A card is just a React component rendered inside the conversation, so adding a feature means adding a component and one entry in a table, not a new route, nav item and layout.

## 3. A pipeline that never lets the model be the only source of truth

```
question → safety pre-check → understand → retrieve → fuse → rerank
        → sufficiency gate → compose with citations → safety post-check → answer
```

Principles we kept:

- **Retrieval before generation.** No passage, no answer.
- **Safety before personalisation**, and personalisation never overrides safety.
- **Only approved documents are retrievable.** Approving is a human step. Approving a document also activates its linked foods and guidelines.
- **Traditional knowledge is labelled traditional.** Always.

## 4. Going offline: a RAG engine with no API key

Midway through we were asked to build the pipeline *without Groq or Gemini*. That turned out to be a gift: it forced a pipeline we could inspect, test and run anywhere (a clinic with poor connectivity, a laptop in CI).

The local engine fuses seven signals with weighted reciprocal-rank fusion:

| Signal | Why it earns its place |
|---|---|
| BM25 | exact vocabulary |
| Character n-gram TF-IDF | OCR damage, spelling and transliteration variants |
| Concept match | a 91-concept ontology with Hindi/Gujarati synonyms |
| LSA semantic space | paraphrase, learned from the corpus itself |
| Structure | the book's chapter and section titles |
| Graph activation | PageRank over a knowledge graph whose edges come from corpus co-occurrence (NPMI) |
| Pseudo-relevance feedback | pull in terms from the best hits |

After fusion: an interpretable rerank, MMR for diversity, then the part that matters most.

### The sufficiency gate

Most RAG demos retrieve *something* and let the model talk. We refuse. An idf-weighted, concept-aware coverage score decides whether the retrieved passages actually cover the question. If not, the answer is *"I don't have a reviewed source for that"* — and the user gets a way forward instead of a guess.

The first time a real user typed *"I want the real answer"* after getting that refusal, we learned the gate was only as good as the knowledge base behind it. The fix wasn't loosening the gate; it was **ingesting more real knowledge** and approving it.

### The composer is extractive

The answer is assembled from the passages themselves, with ordered citations. There is no free-text generation step in the default path, so there is nothing to hallucinate. The cost is prose that is plainer than a language model's. For this domain that is a trade we would make again.

## 5. Turning a damaged OCR scan into knowledge

One source is a scanned, bilingual copy of *Prasuti Tantra*. The OCR is rough: Hindi and English interleaved, headings broken, characters mangled.

What worked:

- **Extract only English prose.** Mixed-script lines are discarded rather than repaired.
- **Recover structure from headings and the table of contents, then verify it against the body text.** A chapter is trusted only if its title is actually found where the contents says it should be.
- **Build a representation, not just chunks:** chapters, sections, concepts per chapter, classical authorities cited (Caraka, Vagbhata…), and a bilingual glossary. The `/book` card is just a view over it.
- **Know when to stop.** Where text is too damaged to quote, the composer points to the printed page.

Result: 567 retrievable chunks and a browsable book.

## 6. Measuring honestly

It is easy to fool yourself with a RAG evaluation. We tuned on one question set, then wrote more sets after the tuning and kept the last one **untouched**.

| Set | Right doc first | Top 3 |
|---|---|---|
| Tuned | 95% | 100% |
| Held-out 1 | 90% | 95% |
| Held-out 2 | 69% | 88% |
| **Held-out 3 (never tuned on)** | **71%** | **86%** |

The gap between 95% and 71% is the honest cost of tuning on what you test. Ablation also showed an uncomfortable truth: a plain lexical baseline (BM25 + n-grams) scores 85.3% against 88.0% for the full pipeline on the mixed set. The fancy signals buy a few points, mostly on paraphrases. We report both numbers and keep every switch in a `Config` so any signal can be ablated.

Known failure modes, written down instead of hidden: paraphrases that share no vocabulary with the source, and rare-word out-of-scope questions that occasionally pass the gate.

## 7. Safety is not a prompt

Safety classification is its own module with its own tests, never delegated to a model, and it **fails closed**.

- Urgent terms are matched in English, Hindi, Hinglish and Gujarati. A user typing *"khoon aa raha hai"* gets an escalation, not a nutrition tip.
- Retrieved text is treated as data, never as instructions.
- An urgent answer carries buttons: a quick safety check, call 112, find a hospital.

The lesson: the phrases are the easy part to build and the hardest part to certify. They need native speakers and clinicians, and we say so in the README.

## 8. From answers to a daily habit

A good Q&A bot is used once. Thinking about *real* use — what a mother types, how she'd come back tomorrow, what she'd take to the clinic — led to five care features:

1. **Dating.** One input (last period, due date, or "I know my week") becomes an exact week, a visit calendar (FOGSI weeks 12, 20, 26, 30, 34, 36, 38, 40, 41), the free PMSMA check-up on the 9th and an iron-folic-acid course from week 16.
2. **Daily check-in** in about 20 seconds, with reminders and streaks.
3. **Readings** — Hb, BP, weight, sugar, typed, pasted from a lab report or photographed (local Tesseract). Parsed values are shown for confirmation *before* saving. Flags cite WHO or ICMR-NIN.
4. **Meals** — *"2 roti, 1 katori dal, curd"* → approximate nutrients from USDA per-100g data, gaps against a pregnancy day, and vegetarian/allergy-aware suggestions. Never liver.
5. **Red-flag screening** and a printable **doctor summary**.

Design rules that kept this honest:

- **Rules live in data**, not code: [`care_rules.yaml`](../backend/app/data/care_rules.yaml) holds every threshold with its source and URL, all marked *pending clinical review*.
- **Consent gates all health data**; withdrawing it purges it; export includes it.
- **The chat can record too**: *"my Hb is 9.8"* is saved, but a question never is.
- **Be upfront about limits**: reminders only show while the app is open; nutrient values are estimates.

See [`care-features.md`](care-features.md) for the full inputs and journey.

## 9. Engineering notes worth sharing

- **Hermetic tests.** The suite blanks every LLM, embedding and search key in `conftest.py`, so a developer's real keys can never make a test pass or fail.
- **Settings, not just `os.environ`.** Early on, keys in `backend/.env` weren't seen because we read the process environment directly. Always go through the settings object.
- **A stemmer is a liability until it's tested.** Inconsistencies (*breastfeed/breastfed*, *exercises/exercise*) quietly dropped recall. We rewrote it and added property tests.
- **Pydantic gotcha:** a field named `date` typed `date | None` shadows the type. Import `date as Date`.
- **Mocked-backend e2e tests** run in CI without an API and caught real regressions (a moved sidebar item broke two tests).
- **Cache headers:** a per-resource cache header fought a global `no-store` middleware, so we reverted rather than clever our way around it.
- **Screenshots are generated, not staged.** The README images come from a script that registers a demo user, seeds readings and meals through the API, and captures the real UI.

## 10. Guard rails: 1,231 rules, and what went wrong on the way

The first safety layer was about fifty phrases. It caught *"heavy bleeding"* but knew nothing about medicines, so the obvious next question, *"can I take paracetamol?"*, went straight to retrieval. The rule we settled on is stricter than any single guideline: **the chat never says yes to a medicine, gives a dose, or tells anyone to start, stop or change one.** It explains and sends the person to a doctor.

That became a rule engine with rules as data: one rule per medicine (918), plus herbs, foods, exposures, warning signs, risky requests and rules tied to the person's own conditions, each with a source, in four languages. A final check on the answer itself replaces anything that gives a dose or calls a medicine safe, whatever wrote it.

What we got wrong first, which is the useful part:

- **We padded.** Our first pass at "1,000+ rules" had separate rules for *olanzapine* and *olanzapine tablet*, dose-number aliases like *atorvastatin 10*, and a few things that were not drugs at all. The count looked right and meant nothing. We deleted the duplicates and now report only what survives, with a test that a phrase triggers one rule per kind.
- **We cried wolf.** Words like *show*, *tea*, *salt*, *weed*, *ice* and *travel* are triggers in some context and ordinary in every other. A fuzzy match turned *mental* into a pain-relief brand. The fix was a test that runs every ordinary question in the retrieval benchmarks through the rules and fails if any is blocked. A guard rail that cries wolf teaches people to ignore it, which is its own safety failure.
- **A question about a warning sign is not a warning sign.** *"What are the warning signs of pre-eclampsia?"* was escalated as a seizure because the word *eclampsia* matched. Now a general question gets information plus one line ("if this is happening to you now, get help"), while *"my baby is moving less"* always escalates.
- **A prescribed medicine is not the same as a stray one.** *"My doctor prescribed Thyronorm, what should I avoid eating?"* should not be refused. It becomes a caution. A drug that harms the baby is never waved through.
- **We almost said too much ourselves.** A refusal about paracetamol first carried the reason *"often the pain medicine doctors consider first"*, which reads like a recommendation. We rewrote it. Reading real replies end to end caught what the tests did not.
- **Hindi and Gujarati broke a regex.** The usual "strip punctuation" pattern deletes Devanagari and Gujarati vowel signs, which Python does not count as letters. A test question in Hindi found it.
- **The honest limit.** The rules were written from public knowledge and cite the reference they are consistent with. Nobody has checked each one against its source, and no clinician or pharmacist has signed them off. Reviewing them is the next job, and [`clinical-review.md`](./clinical-review.md) is written for the reviewer.

## 11. What we would do next

1. **Clinical review** of `care_rules.yaml` and native-speaker review of the Hindi and Gujarati safety phrases. Nothing else matters more before real use.
2. **A pilot** with one clinic: 20–30 mothers for 8 weeks, measuring check-in streaks, visits kept and flags raised.
3. **Push or SMS reminders** — today they only show while the app is open.
4. **More sources**, reviewed by a person: the gate is only as good as what's behind it.
5. **Close the paraphrase gap** with a small local embedding model, kept optional so the engine still runs anywhere.

## 12. Takeaways

- A refusal is a feature. The gate that says *"I can't answer that from a reviewed source"* is what makes every other answer trustworthy.
- Build the offline path first. It makes the system testable, cheap and independent of any vendor.
- Hold out a test set you never touch, and publish the drop.
- Put rules in data with sources attached, so a clinician can review a file instead of reading code.
- One window beats twenty pages.

---

*Code: [`backend/app/rag/local`](../backend/app/rag/local) · [`backend/app/services/care`](../backend/app/services/care) · [`evaluation/local_rag`](../evaluation/local_rag). Back to the [README](../README.md).*
