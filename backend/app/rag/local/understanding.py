"""Query understanding: what kind of question is it, who is it about, and is it really two questions?

Rule-based and transparent -- every decision can be read off the question text and the knowledge graph.

* intent       definition | quantity | safety | how_to | list | comparison | general. Shapes which sentences the
               composer prefers (a definition question wants "X is ..."; a quantity question wants a number).
* authorities  classical authorities named in the question ("what does Caraka say ...").
* sub-queries  "iron and calcium" are retrieved separately when no passage talks about both, so one half of the
               question cannot drown out the other.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.rag.local.authorities import AUTHORITIES
from app.rag.local.graph import KnowledgeGraph
from app.rag.local.text import fold, tokens

_INTENTS: list[tuple[str, re.Pattern[str]]] = [
    ("comparison", re.compile(r"\b(?:differences?|versus|vs|compare[ds]?|comparison|which is better|better than)\b", re.I)),
    ("definition", re.compile(r"^\s*(?:what (?:is|are|was|were)\b(?! the best)|what does .{1,40} mean|define\b|meaning of|explain\b|tell me about\b)", re.I)),
    ("quantity", re.compile(r"\bhow (?:much|many|often|long)\b|\bdose\b|\bdosage\b|\bamount\b|\bquantit|\bportions?\b|\bper day\b", re.I)),
    ("safety", re.compile(r"\b(?:safe|safely|unsafe|harm|harmful|avoid|risk|risky|dangerous|allowed|okay to|ok to|can i (?:eat|drink|take|do|have)|should i (?:avoid|stop))\b", re.I)),
    ("how_to", re.compile(r"\bhow (?:do|can|to|should|would) (?:i|we|you)\b|\bwhat (?:helps?|can i do|should i do)\b|\b(?:ease|relieve|manage|treat|remedy|cure|prevent)\b", re.I)),
    ("list", re.compile(r"^\s*(?:which|what) (?:\w+ ){0,3}(?:foods?|exercises?|signs?|symptoms?|vitamins?|supplements?|medicines?|drugs?|tests?|scans?|vaccines?)\b", re.I)),
]

# an English sentence that states what something is
DEFINITION_PATTERN = re.compile(
    r"\b(?:is|are|was|were|refers? to|means?|denotes?|called|termed|defined as|known as|described as|consists? of)\b", re.I
)


@dataclass
class QueryPlan:
    intent: str = "general"
    authorities: list[str] = field(default_factory=list)
    sub_queries: list[str] = field(default_factory=list)


def intent_of(query: str) -> str:
    for name, pattern in _INTENTS:
        if pattern.search(query):
            return name
    return "general"


def authorities_in(query: str) -> list[str]:
    folded = fold(query)
    return [
        name for name, variants in AUTHORITIES.items()
        if any(re.search(rf"\b{re.escape(fold(v))}", folded) for v in variants)
    ]


def split_compound(query: str, graph: KnowledgeGraph) -> list[str]:
    """Sub-queries for "X and Y" questions whose halves are about different, never-co-mentioned concepts."""
    parts = [p.strip(" ?,.") for p in re.split(r"\band\b|,|;|\bplus\b", query, flags=re.I) if p.strip(" ?,.")]
    if len(parts) < 2 or len(parts) > 3:
        return []
    detected = [set(graph.detect(tokens(p))) for p in parts]
    if any(not d for d in detected):
        return []
    union = set().union(*detected)
    if sum(len(d) for d in detected) != len(union):
        return []  # a concept is shared between the parts: it is one question, not two
    passages_for = [set().union(*(graph.postings.get(c, set()) for c in d)) for d in detected]
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            if passages_for[i] & passages_for[j]:
                return []  # some passage already discusses both: retrieve them together
    return parts


def analyze(query: str, graph: KnowledgeGraph, decompose: bool = True) -> QueryPlan:
    intent = intent_of(query)
    return QueryPlan(
        intent=intent,
        authorities=authorities_in(query),
        sub_queries=split_compound(query, graph) if decompose and intent != "comparison" else [],
    )
