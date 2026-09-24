import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from retrieval.metrics import ndcg_at_k, precision_at_k, recall_at_k, reciprocal_rank


def test_recall_at_k_perfect_recall() -> None:
    assert recall_at_k(["a", "b", "c"], {"a"}, k=3) == 1.0


def test_recall_at_k_relevant_item_outside_k() -> None:
    assert recall_at_k(["a", "b", "c"], {"z"}, k=3) == 0.0


def test_recall_at_k_partial_multi_relevant() -> None:
    assert recall_at_k(["a", "b", "c"], {"a", "z"}, k=3) == 0.5


def test_recall_at_k_no_relevant_items_defined_is_zero() -> None:
    assert recall_at_k(["a", "b"], set(), k=2) == 0.0


def test_precision_at_k_all_hits() -> None:
    assert precision_at_k(["a", "b"], {"a", "b"}, k=2) == 1.0


def test_precision_at_k_no_hits() -> None:
    assert precision_at_k(["a", "b"], {"z"}, k=2) == 0.0


def test_precision_at_k_partial() -> None:
    assert precision_at_k(["a", "b", "c"], {"a"}, k=3) == 1 / 3


def test_reciprocal_rank_first_position() -> None:
    assert reciprocal_rank(["a", "b", "c"], {"a"}) == 1.0


def test_reciprocal_rank_third_position() -> None:
    assert reciprocal_rank(["x", "y", "a"], {"a"}) == 1 / 3


def test_reciprocal_rank_not_found() -> None:
    assert reciprocal_rank(["x", "y"], {"a"}) == 0.0


def test_ndcg_at_k_perfect_ranking_is_one() -> None:
    assert ndcg_at_k(["a", "b"], {"a", "b"}, k=2) == 1.0


def test_ndcg_at_k_relevant_item_first_is_one() -> None:
    assert ndcg_at_k(["a", "x", "y"], {"a"}, k=3) == 1.0


def test_ndcg_at_k_relevant_item_lower_ranked_is_less_than_one() -> None:
    score = ndcg_at_k(["x", "a", "y"], {"a"}, k=3)
    assert 0 < score < 1.0


def test_ndcg_at_k_no_relevant_found_is_zero() -> None:
    assert ndcg_at_k(["x", "y"], {"a"}, k=2) == 0.0


def test_ndcg_at_k_no_relevant_items_defined_is_zero() -> None:
    assert ndcg_at_k(["x", "y"], set(), k=2) == 0.0


def test_repeated_id_in_retrieved_list_is_not_double_counted() -> None:
    """Regression: a single relevant id appearing at multiple ranks (e.g.
    several chunks from the same document, or several documents sharing one
    source_id) must count once, not once per occurrence -- nDCG must never
    exceed 1.0 for a single-relevant-item case."""
    retrieved = ["a", "a", "a", "a", "a"]
    relevant = {"a"}
    assert recall_at_k(retrieved, relevant, k=5) == 1.0
    assert precision_at_k(retrieved, relevant, k=5) == 1 / 5
    assert reciprocal_rank(retrieved, relevant) == 1.0
    assert ndcg_at_k(retrieved, relevant, k=5) == 1.0
