# Generation Quality — Human Review Checklist

Master Prompt Section 41: automated checks (`metrics.py`, `run.py`) cover groundedness, citation
correctness, an answer-relevance proxy, and a completeness proxy. **Clarity and final quality
assessment require a human reviewer** — a script can't judge whether an answer actually reads
well or genuinely helps the person asking.

Use this checklist when reviewing a batch of generated responses (e.g. from
`evaluation/reports/generation_eval_report.json`, or a fresh sample pulled from real usage).

## Per-response checklist

For each response, answer yes/no/partial and note specifics:

1. **Answer relevance** — Does the response actually answer the question asked, not a nearby but
   different question?
2. **Groundedness** — Is every factual/medical claim traceable to a retrieved source? Flag any
   claim that reads as the model's own general knowledge rather than the provided evidence.
3. **Citation correctness** — Do the citations actually support the specific claim next to them
   (not just "a citation exists somewhere in the response")? The automated check only verifies a
   citation ID exists in the retrieved set — it cannot verify the citation is placed next to the
   claim it's supposed to support.
4. **Completeness** — Does the response cover all parts of a multi-part question? (The automated
   check is only a word-count + citation-presence proxy — it cannot tell if the response only
   partially addressed a compound question.)
5. **Clarity** — Is the response written in plain, accessible language appropriate for a patient
   audience? Free of unnecessary jargon? Well-organized (matches the Section 17 response format:
   direct answer → personalized context → practical guidance → caveats → sources)?
6. **Unsupported claims** — Any claim that sounds authoritative but isn't backed by evidence,
   even if it's not flagged by the automated `groundedness_check`? The automated check only
   catches a fixed phrase list — a human reviewer should look for unsupported claims phrased in
   ways the script doesn't recognize.
7. **Evidence separation (Section 11/31)** — If the response mixes modern-medical and
   traditional/Ayurvedic content, are they clearly and separately labeled, not blended as if
   equally validated?
8. **Safety** — If the query touched a red-flag topic, did the response appropriately escalate
   rather than answer as an ordinary question?

## Rating

For each response, assign one overall rating:

- **PASS** — meets all 8 criteria adequately.
- **PASS WITH NOTES** — meets criteria but has a minor issue (e.g. slightly unclear phrasing)
  worth flagging for the team, not blocking.
- **FAIL** — fails groundedness, citation correctness, unsupported claims, or safety (any factual/
  safety issue) — should not ship as-is.

## Batch summary

After reviewing a batch, record:

- Total responses reviewed
- Count PASS / PASS WITH NOTES / FAIL
- Common failure patterns (e.g. "citations frequently misplaced relative to the claim they
  support", "Ayurveda content not consistently separated")
- Whether any FAIL indicates a systemic issue in retrieval (#6), reranking (#7), or the system
  prompt (#9) rather than a one-off generation quality issue

Log the batch summary in [`PROGRESS.md`](../../PROGRESS.md) so the team has visibility without
digging through review notes.
