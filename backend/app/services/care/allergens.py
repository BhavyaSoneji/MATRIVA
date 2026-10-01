"""Allergy handling for food suggestions.

A person types an allergy ("dairy", "tree nuts", "mango"). It is turned into the food words it covers (app/data/allergens.yaml)
and matched as WHOLE words, so "egg" removes Egg but not Eggplant, and "dairy" removes milk, curd, paneer and ghee. An allergy
that matches no group and no food is reported back instead of being ignored, because a silently ignored allergy is the
dangerous case.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_PATH = Path(__file__).resolve().parents[2] / "data" / "allergens.yaml"


@functools.lru_cache(maxsize=1)
def groups() -> dict[str, dict[str, Any]]:
    return yaml.safe_load(_PATH.read_text(encoding="utf-8"))["groups"]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def has_word(text: str, word: str) -> bool:
    """`word` appears in `text` as a whole word or a simple plural of it ("peanut" matches "peanuts", not "eggplant")."""
    return re.search(rf"\b{re.escape(_norm(word))}(?:s|es)?\b", _norm(text)) is not None


@dataclass
class Allergies:
    """What the entered allergies mean: the groups they belong to and any words matched directly."""

    entered: list[str]
    groups: set[str] = field(default_factory=set)
    direct: list[str] = field(default_factory=list)  # entered text with no group, matched on its own (for example "mango")

    @property
    def words(self) -> list[str]:
        out: list[str] = []
        for key in self.groups:
            out.extend(groups()[key]["words"])
        return [*out, *self.direct]

    def labels(self) -> list[str]:
        return sorted(groups()[k]["label"] for k in self.groups)


_FILLER = re.compile(r"\b(allergy|allergies|allergic|to|intolerance|intolerant|sensitivity|sensitive|free|i|am|have|a)\b")


def _clean(entered: str) -> str:
    return re.sub(r"\s+", " ", _FILLER.sub(" ", _norm(entered))).strip()


def resolve(entered: list[str]) -> Allergies:
    result = Allergies(entered=[a for a in entered if a and a.strip()])
    for raw in result.entered:
        text = _clean(raw)
        if not text:
            continue
        matched = {
            key for key, spec in groups().items()
            if any(has_word(text, alias) for alias in spec["aliases"]) or text in [_norm(a) for a in spec.get("exact_aliases", [])]
        }
        if matched:
            result.groups |= matched
        else:
            result.direct.append(text)
    return result


def text_blocked(text: str, allergies: Allergies) -> bool:
    return any(has_word(text, w) for w in allergies.words)


def food_blocked(food: dict[str, Any], allergies: Allergies) -> bool:
    return text_blocked(" ".join([food["name"], *food.get("aliases", [])]), allergies)


def unrecognised(allergies: Allergies, foods: list[dict[str, Any]]) -> list[str]:
    """Entered allergies we could not tie to a known group or to any food in the table."""
    missing = []
    for word in allergies.direct:
        if not any(has_word(" ".join([f["name"], *f.get("aliases", [])]), word) for f in foods):
            missing.append(word)
    return missing
