# Frequently asked questions

## Using it

**Can MATRIVA tell me which medicine to take, or whether one is safe?**
No, and it never will. It will not say yes, give a dose, name a brand to try, or suggest stopping or changing a prescribed medicine, even for a common one such as paracetamol. It explains why and sends you to your doctor or pharmacist. See [`guardrails.md`](./guardrails.md).

**What if I really have a fever or pain and cannot reach a doctor?**
A temperature of 38 C or more in pregnancy needs a doctor the same day. Call your ANM or ASHA, your doctor, or go to the nearest maternity unit. In an emergency call **112**, or 102 for an ambulance. MATRIVA's messages repeat these numbers for that reason.

**Why does it sometimes say "I don't have a reviewed source for that"?**
Only approved documents can answer a question, and a thin match is judged insufficient. A plain refusal is the intended behaviour, not a fault. An admin can approve more documents.

**Why did it refuse to tell me my baby's sex?**
Telling or finding out the sex of an unborn baby is illegal in India under the PCPNDT Act, 1994.

**Why did a harmless question get a warning in front of it?**
Cautions are deliberately cautious: a notice about caffeine, raw papaya or a fall costs a line of reading, a missing one could cost more. Tap "Why MATRIVA answered this way" to see the rule and its source. If a warning is wrong or noisy, please tell us: a guard rail that cries wolf is a bug.

**Does it work in Hindi and Gujarati?**
Questions, warnings and refusals do. Answers drawn from the knowledge base are in English today (issue #86). The Hindi and Gujarati wording has not yet been reviewed by a native speaker (#91).

**Can I use it by voice?**
Yes: speech in and out in the chat, where your browser supports it.

## Data

**Is my health information sent to an AI?**
Not in the default offline engine. Your safety profile (conditions, medicines, allergies) is never sent to a model. See [`privacy.md`](./privacy.md).

**How do I delete everything?**
Settings, **Delete my account**. Deleting only the profile leaves chat history behind.

**Do I have to fill in the safety profile?**
No. It makes warnings personal (a headache is an emergency if you have high blood pressure), and everything works without it.

## The project

**Do I need an API key?**
No. `RAG_ENGINE=local` is the default and is fully offline. Groq and Gemini are optional.

**Can I use it with real patients today?**
No. The care rules, the guard rails and the Hindi and Gujarati text have not been reviewed by a clinician, a pharmacist or a native speaker. See [`clinical-review.md`](./clinical-review.md) for what has to happen first.

**How accurate is the retrieval?**
On questions it was never tuned on, the right document ranks first about 71% of the time and in the top three 86%. Out-of-scope questions are refused 83 to 100% of the time depending on the set. Full tables: [`local-rag.md`](./local-rag.md).

**Where do the food suggestions come from?**
Two places, kept apart: the *Prasuti Tantra*'s month-wise regimen (traditional, quoted with page) and USDA nutrient values. See [`food-guide.md`](./food-guide.md).

**Why does the food guide mention ghee medicated with herbs but not tell me to take it?**
Those are medicines in the book's own terms. MATRIVA lists what the book describes, in a collapsed section marked "not food, not advice", and tells you to ask your doctor and an Ayurvedic physician.

**Why a chat window instead of pages?**
The first version had a page for every feature and nobody knew where to start. One window with commands and inline cards is easier to find your way around and to extend. See the [tech blog](./TECH_BLOG.md).

**What licence is it under?**
None has been chosen yet.
