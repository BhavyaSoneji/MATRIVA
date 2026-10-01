"""What to eat, by month of pregnancy and by need.

Two sources, kept apart and labelled:

* the book's month-wise dietary regimen (Prasuti Tantra, chapter 5): traditional Ayurvedic knowledge, quoted with the
  authority and the scanned page. Herb-medicated preparations and enemas are listed as what the book describes, never as
  advice, because MATRIVA does not advise on medicines or treatments;
* modern food sources for a nutrient, ranked by how much one everyday serving gives, from the USDA table and compared with the
  NIH pregnancy allowance already used by the meal log.

Diet (vegetarian / vegan) and allergies are respected. Foods the guard rails advise against, such as liver, are never suggested.
"""

from __future__ import annotations

import functools
import math
from pathlib import Path
from typing import Any

import yaml

from app.safety.guardrails import load_registry
from app.services.care import allergens
from app.services.care.meals import serving_for
from app.services.care.rules import foods, rules

_PATH = Path(__file__).resolve().parents[2] / "data" / "food_guide.yaml"
MAX_MONTH = 9
# Foods that must not be offered (kept in step with the guard rails: liver is very high in preformed vitamin A).
_NEVER = ("liver",)
_AVOID_IDS = (
    "sub-raw-eggs", "sub-raw-milk", "sub-raw-sprouts", "sub-rare-steak", "sub-undercooked-chicken", "sub-undercooked-pork",
    "sub-deli-meats", "sub-liver-pate", "sub-smoked-salmon", "sub-sushi", "sub-brie", "sub-raw-papaya", "sub-leftover-rice",
    "sub-untreated-water", "sub-pre-cut-melon", "sub-shark", "sub-tuna", "sub-tea", "sub-alcohol",
)


@functools.lru_cache(maxsize=1)
def guide() -> dict[str, Any]:
    return yaml.safe_load(_PATH.read_text(encoding="utf-8"))


def month_of(week: int | None) -> int | None:
    """Pregnancy month (1-9) for a week; the book describes nine months."""
    if not week or week < 1:
        return None
    return min(MAX_MONTH, math.ceil(week / 4.345))


def _allowed(tags: list[str], diet: str | None) -> bool:
    diet = (diet or "").lower()
    if diet in {"vegetarian", "vegan", "eggetarian"} and "non_veg" in tags:
        return False
    return not (diet == "vegan" and "dairy" in tags)


def traditional(month: int | None, diet: str | None, allergies: list[str] | None = None) -> dict[str, Any]:
    g = guide()
    book = dict(g["book"])
    out: dict[str, Any] = {
        "book": book, "evidence_level": "traditional", "month": month,
        "months_available": list(range(1, MAX_MONTH + 1)),
    }
    if month is None:
        return {**out, "foods": [], "medicated": [], "procedures": []}
    items = g["months"][month]["items"]
    avoid = allergens.resolve(allergies or [])
    candidates = [i for i in items if i["kind"] == "food" and _allowed(i.get("tags", []), diet)]
    kept = [i for i in candidates if not allergens.text_blocked(i["text"], avoid)]
    shown = [{k: i[k] for k in ("authority", "text", "page") if k in i} | {"paraphrased": bool(i.get("paraphrased"))} for i in kept]
    skipped = sum(1 for i in items if i["kind"] == "food" and not _allowed(i.get("tags", []), diet))
    out["foods"] = shown
    out["skipped_for_allergy"] = len(candidates) - len(kept)
    out["medicated"] = [{k: i[k] for k in ("authority", "text", "page")} for i in items if i["kind"] == "medicated"]
    out["procedures"] = [{k: i[k] for k in ("authority", "text", "page")} for i in items if i["kind"] == "procedure"]
    out["skipped_for_diet"] = skipped
    out["medicated_note"] = (
        "The book also describes milk, ghee or rice prepared with named herbs, and enemas. These are treatments, not food. "
        "MATRIVA does not advise on them: ask your doctor, and an Ayurvedic physician who knows you are pregnant."
    )
    out["rationale"] = g["rationale"]
    out["avoid"] = g["avoid"]
    return out


def _is_blocked(food: dict[str, Any], banned: set[str], avoid: allergens.Allergies, diet: str | None) -> bool:
    name = food["name"].lower()
    if food["category"] in banned or any(n in name for n in _NEVER):
        return True
    if (diet or "").lower() == "vegetarian" and name.startswith("egg"):
        return True
    return allergens.food_blocked(food, avoid)


def modern(need: str | None, diet: str | None, allergies: list[str]) -> dict[str, Any]:
    g = guide()
    needs = {k: {"id": k, "label": v["label"], "reason": v["reason"]} for k, v in g["needs"].items()}
    out: dict[str, Any] = {"needs": list(needs.values()), "need": None, "foods": []}
    if need is None:
        return out
    spec = g["needs"].get(need)
    if spec is None:
        raise KeyError(need)
    nutrient = spec["nutrient"]
    target = spec.get("target") or rules()["nutrition_targets"]["per_day"].get(nutrient)
    d = (diet or "").lower()
    banned = {"vegetarian": {"meat_fish"}, "eggetarian": {"meat_fish"}, "vegan": {"meat_fish", "dairy_egg"}}.get(d, set())
    avoid = allergens.resolve(allergies)
    ranked = []
    for f in foods().values():
        if _is_blocked(f, banned, avoid, diet):
            continue
        serving = serving_for(f)
        amount = f["per_100g"].get(nutrient, 0.0) * serving / 100
        if amount > 0:
            ranked.append((amount, serving, f))
    ranked.sort(key=lambda t: -t[0])
    rows = [
        {"name": f["name"], "category": f["category"], "serving_g": serving, "amount": round(amount, 1),
         "percent": round(100 * amount / target) if target else None}
        for amount, serving, f in ranked[:8]
    ]
    out["need"] = {
        "id": need, "label": spec["label"], "reason": spec["reason"], "unit": spec["unit"], "daily_allowance": target,
        "tip": spec.get("tip"),
    }
    out["foods"] = rows
    out["allergy_notes"] = allergy_notes(avoid)
    if not rows:
        out["empty_note"] = "None of the foods in this table fits your diet and allergies for this nutrient. Please ask your doctor or dietitian."
    sources = [g["sources"]["values"]]
    sources.append(g["sources"]["allowance"] if need != "fibre" else g["sources"]["fibre"])
    out["sources"] = sources
    return out


def allergy_notes(avoid: allergens.Allergies) -> list[str]:
    notes = []
    if avoid.groups:
        notes.append("Left out because of your allergies: " + ", ".join(avoid.labels()) + ".")
    for word in allergens.unrecognised(avoid, list(foods().values())):
        notes.append(f"We could not match your allergy to \"{word}\" to any food in this list, so nothing was left out for it. Please check each food yourself.")
    return notes


def avoid_foods() -> list[dict[str, Any]]:
    """Foods and habits the guard rails advise against, with the reason and where it comes from."""
    registry = load_registry()
    items = []
    for rid in _AVOID_IDS:
        rule = registry.by_id.get(rid)
        if rule is None:
            continue
        items.append({
            "name": rule.title, "why": rule.why,
            "sources": [{"name": registry.sources[k]["name"], "url": registry.sources[k]["url"]} for k in rule.sources],
        })
    return items


def build(week: int | None, month: int | None, need: str | None, diet: str | None, allergies: list[str]) -> dict[str, Any]:
    m = month or month_of(week)
    return {
        "week": week, "month": m,
        "traditional": traditional(m, diet, allergies),
        "modern": modern(need, diet, allergies),
        "avoid_modern": avoid_foods(),
        "diet": diet,
        "notes": [
            "Foods only. MATRIVA does not advise on medicines, tablets or herbal products: the government iron and folic acid tablets, and "
            "anything else, are for your ANM or doctor to decide.",
            "Nutrient values are approximate (USDA per-100 g values and everyday portions). Traditional entries are the book's, not modern evidence.",
            "Not reviewed by a clinician. If you have a medical condition, diabetes or allergies, ask your doctor or a dietitian for your own plan.",
        ],
    }
