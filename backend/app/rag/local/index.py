"""The in-memory search index: BM25 over stemmed words plus TF-IDF over character n-grams.

Why two lexical signals, with no embedding model: BM25 is precise on whole words; n-gram TF-IDF is
tolerant of the OCR errors and transliteration variants in the Ayurveda text. They are fused later
(see retriever.py). Index size is small -- a few thousand passages -- so everything lives in plain
dicts and builds in well under a second.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.rag.local.text import char_ngrams, tokens

K1 = 1.4
B = 0.75


@dataclass
class Passage:
    """One retrievable chunk plus everything ranking and citation need to know about it."""

    id: str
    text: str
    meta: dict[str, Any] = field(default_factory=dict)
    tokens: list[str] = field(default_factory=list)
    token_set: frozenset[str] = frozenset()


class LocalIndex:
    def __init__(self, passages: list[Passage]) -> None:
        self.passages = passages
        n = len(passages)
        self.size = n

        # ---- BM25 over stemmed words (title/topic words count too, so a section named for its subject is findable)
        self._postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self._lengths: list[int] = []
        for i, p in enumerate(passages):
            toks = p.tokens or tokens(p.text + " " + str(p.meta.get("title", "")))
            p.tokens = toks
            p.token_set = frozenset(toks)
            self._lengths.append(len(toks))
            for term, tf in Counter(toks).items():
                self._postings[term].append((i, tf))
        self._avgdl = (sum(self._lengths) / n) if n else 1.0
        self.df = {t: len(v) for t, v in self._postings.items()}

        # ---- TF-IDF over character n-grams, cosine-normalised
        grams_per_doc = [Counter(char_ngrams(p.text + " " + str(p.meta.get("title", "")))) for p in passages]
        gram_df: Counter[str] = Counter()
        for g in grams_per_doc:
            gram_df.update(g.keys())
        self._gram_idf = {g: math.log((n + 1) / (d + 0.5)) + 1.0 for g, d in gram_df.items()}
        self._gram_postings: dict[str, list[tuple[int, float]]] = defaultdict(list)
        for i, g in enumerate(grams_per_doc):
            weights = {gram: (1 + math.log(tf)) * self._gram_idf[gram] for gram, tf in g.items()}
            norm = math.sqrt(sum(w * w for w in weights.values())) or 1.0
            for gram, w in weights.items():
                self._gram_postings[gram].append((i, w / norm))

    # ------------------------------------------------------------------ scoring
    def idf(self, term: str) -> float:
        d = self.df.get(term, 0)
        return math.log(1 + (self.size - d + 0.5) / (d + 0.5))

    def bm25(self, query_terms: dict[str, float], allowed: set[int] | None = None) -> dict[int, float]:
        """BM25 scores for weighted query terms ({term: weight}); `allowed` restricts to a candidate set."""
        scores: dict[int, float] = defaultdict(float)
        for term, weight in query_terms.items():
            idf = self.idf(term)
            for i, tf in self._postings.get(term, ()):
                if allowed is not None and i not in allowed:
                    continue
                dl = self._lengths[i]
                scores[i] += weight * idf * (tf * (K1 + 1)) / (tf + K1 * (1 - B + B * dl / self._avgdl))
        return scores

    def ngram_cosine(self, text: str, allowed: set[int] | None = None) -> dict[int, float]:
        """Cosine similarity between the query's n-gram vector and each passage's."""
        counts = Counter(char_ngrams(text))
        weights = {g: (1 + math.log(c)) * self._gram_idf[g] for g, c in counts.items() if g in self._gram_idf}
        norm = math.sqrt(sum(w * w for w in weights.values()))
        if not norm:
            return {}
        scores: dict[int, float] = defaultdict(float)
        for gram, w in weights.items():
            for i, dw in self._gram_postings[gram]:
                if allowed is None or i in allowed:
                    scores[i] += (w / norm) * dw
        return scores

    def containing(self, terms: set[str]) -> dict[int, int]:
        """{passage index: how many of `terms` it contains} for passages with at least one."""
        hit: dict[int, int] = defaultdict(int)
        for term in terms:
            for i, _ in self._postings.get(term, ()):
                hit[i] += 1
        return hit
