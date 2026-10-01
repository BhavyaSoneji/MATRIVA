"""Latent semantic analysis: a small, fully offline "embedding" model learned from the knowledge base itself.

BM25 and n-grams only match words that are literally shared. LSA finds passages that are about the same thing
while using different words: terms that keep appearing in the same passages end up close together in a low-dimensional
space, so a question about "anaemia" also reaches passages that say "low haemoglobin" or "iron deficiency".

How it is built (numpy only):
  1. every passage becomes a sublinear-TF x IDF vector over hashed terms (signed feature hashing into
     `BUCKETS` dimensions, so memory stays bounded however large the corpus grows),
  2. a truncated SVD keeps the `DIM` strongest directions (exact for small corpora, randomised for large ones),
  3. passages are their projections; a question is projected the same way and compared by cosine similarity.

It learns only from approved passages and is rebuilt with the index, so it cannot know anything the reviewed
knowledge base does not contain.
"""

from __future__ import annotations

import math
import zlib
from collections import Counter

import numpy as np

BUCKETS = 4096
DIM = 96
EXACT_LIMIT = 2500  # above this many passages use the randomised SVD
MIN_PASSAGES = 24  # below this a semantic space is just noise


def _bucket(term: str) -> tuple[int, float]:
    h = zlib.crc32(term.encode("utf-8"))
    return h % BUCKETS, 1.0 if (h >> 16) & 1 else -1.0


class SemanticSpace:
    def __init__(self, passage_tokens: list[list[str]], idf: dict[str, float]) -> None:
        self.idf = idf
        n = len(passage_tokens)
        self.ready = n >= MIN_PASSAGES
        self.doc_vectors = np.zeros((n, 0), dtype=np.float32)
        self.projection = np.zeros((BUCKETS, 0), dtype=np.float32)
        if not self.ready:
            return
        x = np.zeros((n, BUCKETS), dtype=np.float32)
        for i, toks in enumerate(passage_tokens):
            self._fill(x[i], Counter(toks))
        dim = max(8, min(DIM, n // 4))  # far fewer dimensions than passages, or there is nothing to generalise
        if n <= EXACT_LIMIT:
            _, s, vt = np.linalg.svd(x, full_matrices=False)
            vt = vt[:dim]
        else:  # randomised range finder (Halko et al.)
            rng = np.random.default_rng(7)
            q, _ = np.linalg.qr(x @ rng.standard_normal((BUCKETS, dim + 10)).astype(np.float32))
            for _ in range(2):
                q, _ = np.linalg.qr(x @ (x.T @ q))
            _, s, vt = np.linalg.svd(q.T @ x, full_matrices=False)
            vt = vt[:dim]
        self.projection = vt.T.astype(np.float32)  # BUCKETS x dim
        docs = x @ self.projection
        self.doc_vectors = docs / (np.linalg.norm(docs, axis=1, keepdims=True) + 1e-9)

    def _fill(self, row: np.ndarray, counts: Counter[str]) -> None:
        for term, tf in counts.items():
            b, sign = _bucket(term)
            row[b] += sign * (1 + math.log(tf)) * self.idf.get(term, 1.0)
        norm = float(np.linalg.norm(row))
        if norm:
            row /= norm

    def scores(self, query_tokens: list[str], allowed: set[int] | None = None, floor: float = 0.05) -> dict[int, float]:
        """Cosine similarity of the question to each passage, positive scores only."""
        if not self.ready or not query_tokens:
            return {}
        q = np.zeros(BUCKETS, dtype=np.float32)
        self._fill(q, Counter(query_tokens))
        qv = q @ self.projection
        norm = float(np.linalg.norm(qv))
        if not norm:
            return {}
        sims = self.doc_vectors @ (qv / norm)
        if allowed is not None:
            return {int(i): float(sims[i]) for i in allowed if sims[i] > floor}
        return {int(i): float(v) for i, v in enumerate(sims) if v > floor}

    def similar_terms(self, term: str, candidates: list[str], top: int = 5) -> list[tuple[str, float]]:
        """Which of `candidates` sit closest to `term` in the space (used to explain query expansion)."""
        if not self.ready:
            return []
        def vec(t: str) -> np.ndarray:
            row = np.zeros(BUCKETS, dtype=np.float32)
            b, sign = _bucket(t)
            row[b] = sign
            v = row @ self.projection
            return v / (np.linalg.norm(v) + 1e-9)
        base = vec(term)
        scored = sorted(((float(vec(c) @ base), c) for c in candidates), reverse=True)
        return [(c, s) for s, c in scored[:top]]
