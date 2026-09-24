import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from safety.run import run_evaluation


def test_at_least_15_test_cases() -> None:
    report = run_evaluation()
    assert report["num_cases"] >= 15


def test_all_section_19_risk_categories_covered() -> None:
    report = run_evaluation()
    assert report["all_section_19_categories_covered"]


def test_all_safety_cases_pass() -> None:
    """CI-enforced: every safety test case must classify/route correctly.
    A failure here means the safety classifier regressed."""
    report = run_evaluation()
    failures = [c for c in report["cases"] if not c["passed"]]
    assert not failures, f"safety eval failures: {failures}"


def test_prompt_injection_attempt_case_still_escalates() -> None:
    """The classifier must not be fooled by an injected instruction inside
    the user query itself (Section 52 Test 10)."""
    report = run_evaluation()
    injection_case = next(
        c for c in report["cases"] if c["category_label"] == "prompt_injection_attempt"
    )
    assert injection_case["actual_risk_category"] == "URGENT_ESCALATION"
    assert injection_case["passed"]
