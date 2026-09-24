"""Hallucination / grounding guard (issue #19, Master Prompt Section 43).

Gap this closes: #66's Sprint 0 script (seed_qa.py) already returned a fixed
insufficient-evidence response when retrieval found nothing, but the real
pipeline (#6 hybrid_retrieve -> #7 rerank -> #8 context_packet -> #9 generate)
never got an equivalent check -- it would happily build a context packet with
zero (or only weakly-relevant) sources and hand it to the LLM anyway, which
is exactly the failure mode Section 43 warns about: the model filling the
gap from general knowledge when it should say "I don't know."

The only way to actually guarantee the model can't do that is to never give
it the chance -- so `generate_or_insufficient_evidence` checks evidence
sufficiency BEFORE calling Groq at all, and returns the fixed response
directly (no LLM call) when there's nothing to ground an answer in.
"""

from __future__ import annotations

from app.llm.groq_client import Groq, generate_from_packet
from app.rag.context_packet import ContextPacket
from app.schemas.knowledge import KnowledgeChunk

INSUFFICIENT_EVIDENCE_RESPONSE = (
    "I don't have enough evidence in the available knowledge base to answer that reliably."
)

# 0.0 is the right threshold for "keyword" scoring (#6's fallback path when
# no live embeddings are available): a score of exactly 0 means no keyword
# overlap at all. It is NOT a safe default for "vector" scoring -- cosine
# similarity is rarely exactly 0 for unrelated text, so this threshold would
# silently stop guarding anything once real embeddings are wired in.
# DEFAULT_MIN_SCORE_BY_MODE keys off #6's RetrievalResult.scoring_mode so the
# right threshold is picked automatically instead of relying on every caller
# to remember to override it.
DEFAULT_MIN_SCORE = 0.0
_VECTOR_MIN_SCORE = 0.75  # cosine similarity floor; revisit once real embeddings are live and this can be tuned against actual data
DEFAULT_MIN_SCORE_BY_MODE = {"keyword": DEFAULT_MIN_SCORE, "vector": _VECTOR_MIN_SCORE}


def has_sufficient_evidence(
    scored_chunks: list[tuple[KnowledgeChunk, float]],
    min_score: float | None = None,
    scoring_mode: str = "keyword",
) -> bool:
    """True if at least one retrieved chunk clears the relevance bar.

    `scoring_mode` picks the right default threshold ("keyword" vs "vector",
    see DEFAULT_MIN_SCORE_BY_MODE) -- pass #6's RetrievalResult.scoring_mode
    here rather than relying on the keyword-only default. `min_score`
    overrides the mode-based default explicitly when given.
    """
    if min_score is None:
        min_score = DEFAULT_MIN_SCORE_BY_MODE.get(scoring_mode, DEFAULT_MIN_SCORE)
    return any(score > min_score for _chunk, score in scored_chunks)


def generate_or_insufficient_evidence(
    context_packet: ContextPacket,
    scored_chunks: list[tuple[KnowledgeChunk, float]],
    *,
    min_score: float | None = None,
    scoring_mode: str = "keyword",
    client: Groq | None = None,
    **generate_kwargs,
) -> str:
    """Section 43's guarantee: if evidence is insufficient, return the fixed
    response WITHOUT calling the LLM at all -- the model never gets a chance
    to fill the gap from general knowledge."""
    if not has_sufficient_evidence(scored_chunks, min_score=min_score, scoring_mode=scoring_mode):
        return INSUFFICIENT_EVIDENCE_RESPONSE
    return generate_from_packet(context_packet, client=client, **generate_kwargs)
