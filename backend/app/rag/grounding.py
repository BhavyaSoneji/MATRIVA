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

# 0.0 is the right threshold for keyword-overlap scoring (#6's fallback path
# when no live embeddings are available): a score of exactly 0 means no
# keyword overlap at all. Once #5's real embeddings are wired into
# hybrid_retrieve's vector path, this threshold should be revisited --
# cosine similarity scores are rarely exactly 0 for unrelated text, so a
# small positive threshold would likely be needed instead.
DEFAULT_MIN_SCORE = 0.0


def has_sufficient_evidence(
    scored_chunks: list[tuple[KnowledgeChunk, float]], min_score: float = DEFAULT_MIN_SCORE
) -> bool:
    """True if at least one retrieved chunk clears the relevance bar."""
    return any(score > min_score for _chunk, score in scored_chunks)


def generate_or_insufficient_evidence(
    context_packet: ContextPacket,
    scored_chunks: list[tuple[KnowledgeChunk, float]],
    *,
    min_score: float = DEFAULT_MIN_SCORE,
    client: Groq | None = None,
    **generate_kwargs,
) -> str:
    """Section 43's guarantee: if evidence is insufficient, return the fixed
    response WITHOUT calling the LLM at all -- the model never gets a chance
    to fill the gap from general knowledge."""
    if not has_sufficient_evidence(scored_chunks, min_score=min_score):
        return INSUFFICIENT_EVIDENCE_RESPONSE
    return generate_from_packet(context_packet, client=client, **generate_kwargs)
