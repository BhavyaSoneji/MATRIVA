"""Meal log and nutrient gaps.

The user types what they ate ("2 roti, 1 katori dal, curd, banana"). Each food is matched to a USDA record (per-100 g
values, app/data/foods_nutrients.json), portions are converted to grams with everyday units, and the day's total is compared
with the pregnancy allowance (care_rules.yaml). Portions and Indian-food matches are approximate and said to be.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MealLog, User
from app.services.care.rules import foods, rules

_WORD_NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "half": 0.5}
_SPLIT = re.compile(r"\s*(?:,|;|\n|\+|\band\b|\bwith\b|\bplus\b|&)\s*", re.I)
_CHUNK = re.compile(
    r"^\s*(?P<q>\d+(?:\.\d+)?(?:\s*/\s*\d+)?|a|an|one|two|three|four|five|six|half)?\s*"
    r"(?P<u>katoris?|bowls?|cups?|glass(?:es)?|tbsp|tsp|handfuls?|pieces?|pcs|slices?|grams?|gms?|g|ml)?\s*(?:of\s+)?(?P<name>.+?)\s*$",
    re.I,
)
_NOISE = re.compile(r"\b(cooked|boiled|fried|fresh|raw|plain|small|large|medium|some|little|bit of|the|my|for|lunch|dinner|breakfast|snack)\b", re.I)
_UNIT_NORMAL = {"katoris": "katori", "bowls": "bowl", "cups": "cup", "glasses": "glass", "handfuls": "handful", "pieces": "piece",
                "pcs": "piece", "slices": "slice", "grams": "g", "gm": "g", "gms": "g", "gram": "g"}
MAX_GRAMS = 2000


def _number(token: str | None) -> float | None:
    if not token:
        return None
    token = token.strip().lower()
    if token in _WORD_NUMBERS:
        return float(_WORD_NUMBERS[token])
    if "/" in token:
        a, b = token.replace(" ", "").split("/")
        return float(a) / float(b)
    return float(token)


def _match_food(name: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """(structured food, alias entry) for the longest matching alias in `name`, or None."""
    text = f" {name.lower()} "
    aliases = rules()["food_aliases"]
    best: tuple[int, str, dict[str, Any]] | None = None
    for alias, entry in aliases.items():
        if re.search(rf"\b{re.escape(alias)}\b", text) and (best is None or len(alias) > best[0]):
            best = (len(alias), alias, entry)
    if best:
        return foods()[best[2]["food"]], best[2]
    for food in foods().values():
        for alias in food["aliases"]:
            if re.search(rf"\b{re.escape(alias)}s?\b", text) and (best is None or len(alias) > best[0]):
                best = (len(alias), alias, {"food": food["id"]})
    return (foods()[best[2]["food"]], best[2]) if best else None


def parse_meal(text: str) -> dict[str, list[Any]]:
    """{'items': [...], 'unknown': [words we could not match]} -- never guesses a food it does not know."""
    cfg = rules()
    items, unknown = [], []
    for chunk in _SPLIT.split(text):
        chunk = chunk.strip()
        if not chunk:
            continue
        m = _CHUNK.match(_NOISE.sub(" ", chunk))
        if not m or not m.group("name").strip():
            continue
        qty, unit = _number(m.group("q")), (m.group("u") or "").lower()
        unit = _UNIT_NORMAL.get(unit, unit)
        found = _match_food(m.group("name"))
        if found is None:
            unknown.append(chunk)
            continue
        food, entry = found
        if unit and unit in cfg["portions"]:
            grams, how = (qty or 1) * cfg["portions"][unit], f"{qty or 1:g} {unit}"
        elif entry.get("piece_g") and (qty is not None or not entry.get("serving_g")):
            grams, how = (qty or 1) * entry["piece_g"], f"{qty or 1:g} piece"
        else:
            serving = entry.get("serving_g") or cfg["default_serving_g"][food["category"]]
            grams, how = (qty or 1) * serving, f"{qty or 1:g} serving"
        items.append({
            "food_id": food["id"], "name": food["name"], "grams": round(min(grams, MAX_GRAMS), 1), "portion": how,
            "approximate": True, "note": entry.get("note"), "text": chunk,
        })
    return {"items": items, "unknown": unknown}


def nutrients_of(items: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for it in items:
        per100 = foods()[it["food_id"]]["per_100g"]
        for k, v in per100.items():
            totals[k] = totals.get(k, 0.0) + v * it["grams"] / 100.0
    return {k: round(v, 1) for k, v in totals.items()}


def log(db: Session, user: User, day: date, text: str, meal_type: str | None = None) -> tuple[MealLog | None, dict[str, list[Any]]]:
    parsed = parse_meal(text)
    if not parsed["items"]:
        return None, parsed
    row = MealLog(user_id=user.id, meal_date=day, meal_type=meal_type, raw_text=text[:500], items=parsed["items"], totals=nutrients_of(parsed["items"]))
    db.add(row)
    db.flush()
    return row, parsed


def day_totals(db: Session, user: User, day: date) -> tuple[list[MealLog], dict[str, float]]:
    rows = list(db.execute(select(MealLog).where(MealLog.user_id == user.id, MealLog.meal_date == day).order_by(MealLog.created_at)).scalars().all())
    totals: dict[str, float] = {}
    for r in rows:
        for k, v in (r.totals or {}).items():
            totals[k] = totals.get(k, 0.0) + v
    return rows, {k: round(v, 1) for k, v in totals.items()}


GAP_NUTRIENTS = ("iron", "calcium", "folate (DFE)", "protein", "vitamin C")
_SERVING_FOR_SUGGESTION = {"legume": 150, "grain": 150, "dairy_egg": 150, "meat_fish": 100, "vegetable": 100, "fruit": 100, "nut_seed": 30}
# The USDA values for these are for the dry grain or the seed, so a realistic serving is smaller than the category default.
_DRY_GRAINS = ("amaranth grain", "oats", "sorghum", "whole wheat flour")
_SEEDS = ("flaxseed", "chia", "sesame", "pumpkin seeds")


def serving_for(food: dict[str, Any]) -> int:
    """An everyday serving in grams for suggesting a food (not for parsing what someone ate)."""
    name = food["name"].lower()
    if name.startswith(_DRY_GRAINS):
        return 50
    if name.startswith(_SEEDS):
        return 15
    if name.startswith("ghee"):
        return 10
    if name.startswith("whole wheat bread"):
        return 60  # two slices
    if name.startswith(("dried figs", "dates", "raisins")):
        return 40
    return _SERVING_FOR_SUGGESTION[food["category"]]


def gaps(totals: dict[str, float], diet: str | None = None, allergies: list[str] | None = None) -> dict[str, Any]:
    targets = rules()["nutrition_targets"]["per_day"]
    rows = []
    for n in GAP_NUTRIENTS:
        intake, target = totals.get(n, 0.0), targets[n]
        rows.append({"nutrient": n, "intake": round(intake, 1), "target": target, "percent": round(100 * intake / target)})
    rows.sort(key=lambda r: r["percent"])
    return {"rows": rows, "suggestions": _suggest([r["nutrient"] for r in rows if r["percent"] < 70][:2], diet, allergies or [])}


def _suggest(low: list[str], diet: str | None, allergies: list[str]) -> list[dict[str, Any]]:
    banned = {"vegetarian": {"meat_fish"}, "vegan": {"meat_fish", "dairy_egg"}}.get((diet or "").lower(), set())
    blocked = [a.lower() for a in allergies]
    out = []
    for nutrient in low:
        ranked = []
        for f in foods().values():
            if f["category"] in banned or any(b in f["name"].lower() or b in " ".join(f["aliases"]) for b in blocked):
                continue
            if f["name"].lower().startswith(("chicken liver",)):
                continue  # NHS advises avoiding liver in pregnancy
            amount = f["per_100g"].get(nutrient, 0.0) * serving_for(f) / 100
            ranked.append((amount, f))
        ranked.sort(key=lambda t: -t[0])
        out.append({"nutrient": nutrient, "foods": [{"name": f["name"], "serving_g": serving_for(f), "amount": round(a, 1)} for a, f in ranked[:4]]})
    return out
