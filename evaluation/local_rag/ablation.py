"""Ablation study: what does each retrieval signal contribute?

Runs the three development question sets (questions.yaml, heldout.yaml, heldout2.yaml) with one signal switched off at a
time, and with only the lexical baseline. heldout3.yaml is excluded: it is the clean test and is run once separately.

Usage:  python evaluation/local_rag/ablation.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path

_HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("local_rag_run", _HERE / "run.py")
run = importlib.util.module_from_spec(spec)
sys.modules["local_rag_run"] = run
spec.loader.exec_module(run)

SETS = ["questions.yaml", "heldout.yaml", "heldout2.yaml"]
OFF = ["semantic", "structure", "graph", "feedback", "concept", "ngram", "authority", "decompose"]
LEXICAL_ONLY = dict(semantic=False, structure=False, graph=False, feedback=False, concept=False, authority=False, decompose=False)


def score(config) -> dict:
    engine = run.Engine(run.build_passages(True))
    totals = {"n": 0, "hit1": 0.0, "hit3": 0.0, "mrr": 0.0, "answered": 0.0, "oos": 0, "refused": 0}
    for name in SETS:
        m = run.evaluate(questions=_HERE / name, config=config, engine=engine)["metrics"]
        n = m["in_scope"]
        totals["n"] += n
        totals["hit1"] += m["hit_at_1"] * n
        totals["hit3"] += m["hit_at_3"] * n
        totals["mrr"] += m["mrr"] * n
        totals["answered"] += m["answered_in_scope"] * n
        totals["oos"] += m["out_of_scope"]
        totals["refused"] += m["refusal_precision"] * m["out_of_scope"]
    n = totals["n"]
    return {"hit@1": round(totals["hit1"] / n, 3), "hit@3": round(totals["hit3"] / n, 3), "MRR": round(totals["mrr"] / n, 3),
            "answered": round(totals["answered"] / n, 3), "refused": round(totals["refused"] / totals["oos"], 3)}


def main() -> int:
    full = run.DEFAULT_CONFIG
    rows = {"full pipeline": score(full), "lexical only (BM25 + n-grams)": score(replace(full, **LEXICAL_ONLY))}
    for signal in OFF:
        rows[f"without {signal}"] = score(replace(full, **{signal: False}))
    width = max(len(k) for k in rows)
    print(f"{'configuration':<{width}}  hit@1  hit@3   MRR  answered  refused")
    for name, r in rows.items():
        print(f"{name:<{width}}  {r['hit@1']:.3f}  {r['hit@3']:.3f}  {r['MRR']:.3f}   {r['answered']:.3f}   {r['refused']:.3f}")
    (_HERE.parent / "reports" / "local_rag_ablation.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
