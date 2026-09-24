"""Personalized query rewriting (issue #11, Master Prompt Section 12 Step 5 + Section 23).

Generates expanded retrieval queries from a raw question + user profile
(pregnancy stage, diet, region, restrictions), e.g. "What can I eat?" ->
["What can I eat?", "What can I eat? second_trimester", "What can I eat?
vegetarian diet", ...]. This ONLY selects/combines existing profile terms
into query variants for #6's retrieval to search with -- it never invents
medical guidance itself (Section 23).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UserProfile:
    pregnancy_stage: str | None = None
    diet: str | None = None
    region: str | None = None
    restrictions: list[str] = field(default_factory=list)


def rewrite_query(raw_query: str, profile: UserProfile) -> list[str]:
    """Return a list of retrieval-query variants: the original query plus one
    variant per known personalization dimension (Section 12 Step 5's example:
    pregnancy nutrition + stage + dietary preference + region + restrictions)."""
    queries = [raw_query]

    if profile.pregnancy_stage:
        queries.append(f"{raw_query} {profile.pregnancy_stage}")
    if profile.diet:
        queries.append(f"{raw_query} {profile.diet} diet")
    if profile.region:
        queries.append(f"{raw_query} {profile.region} regional")
    for restriction in profile.restrictions:
        queries.append(f"{raw_query} {restriction}")

    return queries
