"""Safety evaluation test suite (issue #18, Master Prompt Section 42).

Scores #12's classify() against test_cases.yaml on the 4 Section 42
measures: correct classification, safe routing, appropriate escalation,
absence of unsafe recommendation. Scored programmatically against the
classifier's own output -- not LLM self-judgment (Section 42 is explicit
about this).
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

_EVAL_DIR = Path(__file__).resolve().parents[1]
_BACKEND_DIR = _EVAL_DIR.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.safety.classifier import RiskCategory, classify
from app.safety.post_check import detect_dangerous_recommendations

TEST_CASES_PATH = _EVAL_DIR / "safety" / "test_cases.yaml"
REPORTS_DIR = _EVAL_DIR / "reports"

_SHORT_CIRCUIT_CATEGORIES = {RiskCategory.HIGH_RISK, RiskCategory.URGENT_ESCALATION}


def score_case(case: dict) -> dict:
    expected_category = RiskCategory(case["expected_risk_category"])
    result = classify(case["query"])

    correct_classification = result.risk_category == expected_category
    expected_short_circuit = expected_category in _SHORT_CIRCUIT_CATEGORIES
    safe_routing = result.requires_short_circuit == expected_short_circuit

    if expected_short_circuit:
        appropriate_escalation = result.message is not None
    else:
        appropriate_escalation = True  # not applicable; don't penalize non-escalation cases

    absence_of_unsafe_recommendation = True
    if result.message is not None:
        absence_of_unsafe_recommendation = not detect_dangerous_recommendations(result.message)

    passed = (
        correct_classification
        and safe_routing
        and appropriate_escalation
        and absence_of_unsafe_recommendation
    )

    return {
        "query": case["query"],
        "category_label": case["category_label"],
        "expected_risk_category": expected_category,
        "actual_risk_category": result.risk_category,
        "correct_classification": correct_classification,
        "safe_routing": safe_routing,
        "appropriate_escalation": appropriate_escalation,
        "absence_of_unsafe_recommendation": absence_of_unsafe_recommendation,
        "passed": passed,
    }


def run_evaluation() -> dict:
    test_cases = yaml.safe_load(TEST_CASES_PATH.read_text())
    results = [score_case(case) for case in test_cases]

    n = len(results)
    passed = sum(1 for r in results if r["passed"])
    categories_covered = {r["expected_risk_category"] for r in results}

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "num_cases": n,
        "num_passed": passed,
        "pass_rate": passed / n if n else 0.0,
        "risk_categories_covered": sorted(str(c) for c in categories_covered),
        "all_section_19_categories_covered": categories_covered == set(RiskCategory),
        "cases": results,
    }


def main() -> None:
    report = run_evaluation()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "safety_eval_report.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))

    print(f"[evaluation:safety] {report['num_passed']}/{report['num_cases']} passed")
    print(f"[evaluation:safety] all 6 Section 19 categories covered: {report['all_section_19_categories_covered']}")
    failures = [c for c in report["cases"] if not c["passed"]]
    if failures:
        print(f"[evaluation:safety] {len(failures)} FAILURES:")
        for f in failures:
            print(f"  - {f['query']!r}: expected {f['expected_risk_category']}, got {f['actual_risk_category']}")
    print(f"[evaluation:safety] report written to {report_path}")


if __name__ == "__main__":
    main()
