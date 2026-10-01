"""Quality gate for the offline RAG engine, on the project's real corpus (guidelines, foods, book).

If a change to tokenising, fusion, reranking or the sufficiency gate makes retrieval worse -- or lets the engine
answer an out-of-scope question -- this fails. Thresholds sit slightly below today's numbers
(see evaluation/reports/local_rag_eval_report.json) so ordinary tuning has room.
"""

import importlib.util
from pathlib import Path

RUN = Path(__file__).resolve().parents[2] / "evaluation" / "local_rag" / "run.py"


def _load():
    spec = importlib.util.spec_from_file_location("local_rag_eval", RUN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_retrieval_quality_and_refusals_on_the_real_corpus() -> None:
    report = _load().evaluate(include_book=True)
    m = report["metrics"]
    assert m["passages"] > 600, "the book sections should be part of the corpus"
    assert m["hit_at_3"] >= 0.95, report["in_scope_cases"]
    assert m["mrr"] >= 0.85
    assert m["answered_in_scope"] >= 0.88
    assert m["refusal_precision"] >= 0.90, [c for c in report["out_of_scope_cases"] if not c["refused"]]


def test_modern_questions_do_not_depend_on_the_book() -> None:
    m = _load().evaluate(include_book=False)["metrics"]
    assert m["hit_at_3"] >= 0.95 and m["refusal_precision"] >= 0.85


def test_held_out_sets_do_not_regress() -> None:
    """Floors for the paraphrase sets (numbers in docs/local-rag.md); they catch a change that overfits the tuned set."""
    mod = _load()
    here = RUN.parent
    engine = mod.Engine(mod.build_passages(True))
    floors = {"heldout.yaml": (0.90, 0.80), "heldout2.yaml": (0.80, 0.80), "heldout3.yaml": (0.80, 0.70)}
    for name, (hit3, refusal) in floors.items():
        m = mod.evaluate(questions=here / name, engine=engine)["metrics"]
        assert m["hit_at_3"] >= hit3 and m["refusal_precision"] >= refusal, (name, m)
