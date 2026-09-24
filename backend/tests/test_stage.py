import pytest

from app.services.stage import calculate_stage


@pytest.mark.parametrize(
    ("week", "trimester", "stage"),
    [
        (1, 1, "first_trimester"),
        (13, 1, "first_trimester"),
        (14, 2, "second_trimester"),
        (27, 2, "second_trimester"),
        (28, 3, "third_trimester"),
        (42, 3, "third_trimester"),
    ],
)
def test_stage_boundaries(week: int, trimester: int, stage: str) -> None:
    result = calculate_stage(week)
    assert result.trimester == trimester
    assert result.stage == stage


@pytest.mark.parametrize("week", [0, 43, True, "14"])
def test_invalid_stage(week: object) -> None:
    with pytest.raises(ValueError):
        calculate_stage(week)  # type: ignore[arg-type]
