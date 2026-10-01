"""The knowledge graph: concepts from the ontology, linked by what the reviewed passages say.

Representation
  * Nodes are concepts (iron, ragi, nausea, garbha, ...) from app/data/ontology.yaml. Each node has a type
    and an optional `parent` (is-a hierarchy).
  * Edges are NOT hand-written. Two concepts are connected when they are mentioned in the same approved
    passage, and the edge weight is their normalised pointwise mutual information (NPMI) across the
    corpus -- so "iron" links strongly to "anaemia" only if the sources really keep mentioning them
    together. Every edge also remembers which passages produced it, so any link can be traced to text.
  * Each concept keeps a posting list of the passages that mention it.

Uses in the pipeline: spot concepts in a question, widen the search to strongly related concepts, boost
passages that cover the question's concepts, and draw the knowledge-map card in the chat.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any

import yaml

from app.rag.local.text import tokens

ONTOLOGY_PATH = Path(__file__).resolve().parents[2] / "data" / "ontology.yaml"
_MAX_PHRASE = 4  # longest synonym measured in content tokens


@dataclass(frozen=True)
class Concept:
    id: str
    label: str
    type: str
    parent: str | None
    phrases: tuple[tuple[str, ...], ...]  # each synonym as a tuple of stemmed tokens


def load_concepts(path: Path = ONTOLOGY_PATH) -> tuple[dict[str, Concept], dict[str, str]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    concepts: dict[str, Concept] = {}
    for raw in data["concepts"]:
        names = [raw["label"], raw["id"].replace("_", " "), *raw.get("synonyms", [])]
        phrases = []
        for name in names:
            toks = tuple(tokens(name))
            if toks and len(toks) <= _MAX_PHRASE and toks not in phrases:
                phrases.append(toks)
        concepts[raw["id"]] = Concept(raw["id"], raw["label"], raw["type"], raw.get("parent"), tuple(phrases))
    return concepts, data.get("types", {})


@dataclass
class KnowledgeGraph:
    concepts: dict[str, Concept]
    type_labels: dict[str, str]
    passage_concepts: list[frozenset[str]] = field(default_factory=list)
    postings: dict[str, set[int]] = field(default_factory=dict)
    edges: dict[tuple[str, str], tuple[float, int]] = field(default_factory=dict)  # (a,b) -> (npmi, passages)
    _phrase_index: dict[tuple[str, ...], list[str]] = field(default_factory=dict)
    _adjacency: dict[str, list[tuple[str, float]]] = field(default_factory=dict)

    # -------------------------------------------------------------- build
    @classmethod
    def build(cls, passage_tokens: list[list[str]], concepts: dict[str, Concept] | None = None,
              type_labels: dict[str, str] | None = None) -> KnowledgeGraph:
        if concepts is None:
            concepts, type_labels = load_concepts()
        graph = cls(concepts=concepts, type_labels=type_labels or {})
        for cid, concept in concepts.items():
            for phrase in concept.phrases:
                graph._phrase_index.setdefault(phrase, []).append(cid)

        postings: dict[str, set[int]] = defaultdict(set)
        pair_passages: dict[tuple[str, str], int] = defaultdict(int)
        for i, toks in enumerate(passage_tokens):
            found = graph.detect(toks)
            graph.passage_concepts.append(frozenset(found))
            for cid in found:
                postings[cid].add(i)
            for a, b in combinations(sorted(found), 2):
                pair_passages[(a, b)] += 1
        graph.postings = dict(postings)

        n = max(len(passage_tokens), 1)
        for (a, b), c_ab in pair_passages.items():
            c_a, c_b = len(postings[a]), len(postings[b])
            if c_ab < 2:
                continue
            p_ab = c_ab / n
            pmi = math.log(p_ab / ((c_a / n) * (c_b / n)))
            npmi = pmi / -math.log(p_ab) if p_ab < 1 else 0.0
            if npmi > 0:
                graph.edges[(a, b)] = (round(npmi, 4), c_ab)
        return graph

    # -------------------------------------------------------------- detect
    def detect(self, toks: list[str]) -> list[str]:
        """Concept ids mentioned in a token list, in order of first mention, longest phrase first."""
        found: list[str] = []
        i = 0
        while i < len(toks):
            matched = 0
            for length in range(min(_MAX_PHRASE, len(toks) - i), 0, -1):
                ids = self._phrase_index.get(tuple(toks[i : i + length]))
                if ids:
                    for cid in ids:
                        if cid not in found:
                            found.append(cid)
                    matched = length
                    break
            i += max(matched, 1)
        return found

    def detect_spans(self, toks: list[str]) -> dict[str, set[str]]:
        """{concept id: the question tokens that named it}, e.g. "kicks" names reduced_movement. Lets a paraphrase
        count as covered when a passage mentions the concept in different words ("baby's movements")."""
        out: dict[str, set[str]] = {}
        i = 0
        while i < len(toks):
            matched = 0
            for length in range(min(_MAX_PHRASE, len(toks) - i), 0, -1):
                ids = self._phrase_index.get(tuple(toks[i : i + length]))
                if ids:
                    for cid in ids:
                        out.setdefault(cid, set()).update(toks[i : i + length])
                    matched = length
                    break
            i += max(matched, 1)
        return out

    def detect_text(self, text: str) -> list[str]:
        return self.detect(tokens(text))

    # -------------------------------------------------------------- navigate
    def neighbors(self, cid: str, k: int = 6, min_npmi: float = 0.05) -> list[tuple[str, float, int]]:
        out = []
        for (a, b), (npmi, count) in self.edges.items():
            if cid in (a, b) and npmi >= min_npmi:
                out.append((b if a == cid else a, npmi, count))
        out.sort(key=lambda t: (-t[1], -t[2]))
        return out[:k]

    def relatives(self, cid: str) -> list[str]:
        """Parent and children in the is-a hierarchy."""
        concept = self.concepts[cid]
        rel = [concept.parent] if concept.parent in self.concepts else []
        rel += [c.id for c in self.concepts.values() if c.parent == cid]
        return rel

    def expand(self, cids: list[str], per_concept: int = 3, min_npmi: float = 0.12) -> dict[str, float]:
        """Related concepts worth adding to a search, with a weight in (0, 1]: hierarchy relatives get 0.6,
        corpus neighbours get their NPMI. Concepts already in `cids` are never returned."""
        out: dict[str, float] = {}
        for cid in cids:
            if cid not in self.concepts:
                continue
            for rel in self.relatives(cid):
                out[rel] = max(out.get(rel, 0.0), 0.6)
            for other, npmi, _ in self.neighbors(cid, per_concept, min_npmi):
                out[other] = max(out.get(other, 0.0), npmi)
        for cid in cids:
            out.pop(cid, None)
        return out

    def activation(self, seeds: dict[str, float], alpha: float = 0.5, iterations: int = 20) -> dict[str, float]:
        """Personalised PageRank from `seeds` over the concept graph (graph-RAG style multi-hop reasoning).

        A question about "iron" activates iron, spreads some activation to anaemia and folate (concepts the passages
        keep mentioning with it), a little further to their neighbours, and so on. `alpha` is the share of activation
        that keeps flowing outwards each step; the rest returns to the seeds, so activation stays anchored on what
        the user actually asked about. Returns {concept: activation}, summing to 1.
        """
        seeds = {c: w for c, w in seeds.items() if c in self.concepts and w > 0}
        if not seeds:
            return {}
        if not self._adjacency:
            nbrs: dict[str, list[tuple[str, float]]] = defaultdict(list)
            for (a, b), (w, _) in self.edges.items():
                nbrs[a].append((b, w))
                nbrs[b].append((a, w))
            self._adjacency = {c: [(n, w / sum(x for _, x in lst)) for n, w in lst] for c, lst in nbrs.items()}
        total = sum(seeds.values())
        restart = {c: w / total for c, w in seeds.items()}
        rank = dict(restart)
        for _ in range(iterations):
            nxt: dict[str, float] = defaultdict(float)
            for c, mass in rank.items():
                out = self._adjacency.get(c)
                if not out:
                    nxt[c] += alpha * mass  # a dead end keeps its mass
                    continue
                for n, w in out:
                    nxt[n] += alpha * mass * w
            for c, r in restart.items():
                nxt[c] += (1 - alpha) * r
            norm = sum(nxt.values()) or 1.0
            rank = {c: v / norm for c, v in nxt.items()}
        return rank

    def subgraph(self, cids: list[str], neighbours_each: int = 5, max_nodes: int = 18) -> dict[str, Any]:
        """Nodes and edges around `cids` for the knowledge-map card."""
        nodes: dict[str, dict[str, Any]] = {}

        def add(cid: str, focus: bool) -> None:
            c = self.concepts[cid]
            nodes.setdefault(
                cid,
                {"id": cid, "label": c.label, "type": c.type, "focus": focus, "passages": len(self.postings.get(cid, ()))},
            )

        for cid in cids:
            if cid in self.concepts:
                add(cid, True)
        for cid in list(nodes):
            for other, _, _ in self.neighbors(cid, neighbours_each):
                if len(nodes) < max_nodes:
                    add(other, False)
        edges = [
            {"source": a, "target": b, "weight": w, "passages": n}
            for (a, b), (w, n) in self.edges.items()
            if a in nodes and b in nodes
        ]
        return {"nodes": list(nodes.values()), "edges": edges, "types": self.type_labels}

    def stats(self) -> dict[str, int]:
        return {
            "concepts": len(self.concepts),
            "concepts_found": len(self.postings),
            "edges": len(self.edges),
            "passages": len(self.passage_concepts),
        }
