from dataclasses import dataclass


@dataclass(frozen=True)
class PregnancyStage:
    week: int
    trimester: int
    stage: str


def calculate_stage(week: int) -> PregnancyStage:
    """Calculate a deterministic stage label without making clinical claims."""

    if not isinstance(week, int) or isinstance(week, bool) or not 1 <= week <= 42:
        raise ValueError("pregnancy week must be between 1 and 42")
    if week <= 13:
        trimester, stage = 1, "first_trimester"
    elif week <= 27:
        trimester, stage = 2, "second_trimester"
    else:
        trimester, stage = 3, "third_trimester"
    return PregnancyStage(week=week, trimester=trimester, stage=stage)
