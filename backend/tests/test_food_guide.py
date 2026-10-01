"""The food guide: the book's month-wise regimen and modern food sources for a nutrient."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from app.services.care import foodguide
from app.services.care.rules import foods

REPO = Path(__file__).resolve().parents[2]


def test_the_book_has_every_month_and_every_entry_names_its_authority_and_page() -> None:
    months = foodguide.guide()["months"]
    assert sorted(months) == list(range(1, 10))
    for month, block in months.items():
        assert block["items"], month
        for item in block["items"]:
            assert item["authority"] and item["text"].strip(), (month, item)
            assert 135 <= item["page"] <= 142, (month, item)
            assert item["kind"] in {"food", "medicated", "procedure"}
            assert set(item.get("tags", [])) <= {"dairy", "non_veg"}


def test_book_wording_really_is_in_the_scanned_text() -> None:
    """Quoted entries (not marked paraphrased) must appear in the OCR of the book, so nothing is invented."""
    ocr = (REPO / "knowledge" / "ayurveda" / "Prasuti-Tantra-OCR.txt").read_text(encoding="utf-8")
    flat = re.sub(r"[^a-z]+", "", ocr.lower())
    missing = []
    for month, block in foodguide.guide()["months"].items():
        for item in block["items"]:
            if item.get("paraphrased"):
                continue
            words = re.sub(r"[^a-z]+", "", item["text"].lower())
            # OCR has typos ("sasft", "Vasbhata"), so require two thirds of the sentence in overlapping chunks
            chunks = [words[i : i + 12] for i in range(0, max(1, len(words) - 12), 12)]
            hits = sum(1 for c in chunks if c in flat)
            if hits < max(1, int(len(chunks) * 0.5)):
                missing.append((month, item["authority"], item["text"][:50]))
    assert missing == []


def test_month_from_week() -> None:
    assert foodguide.month_of(None) is None
    assert [foodguide.month_of(w) for w in (1, 4, 5, 13, 21, 36, 40)] == [1, 1, 2, 3, 5, 9, 9]


def test_medicated_preparations_and_enemas_are_never_listed_as_food() -> None:
    for month in range(1, 10):
        t = foodguide.traditional(month, None)
        assert all("ghrta medicated" not in f["text"].lower() and "enema" not in f["text"].lower() for f in t["foods"])
        assert "MATRIVA does not advise" in t["medicated_note"]
    month1 = foodguide.traditional(1, None)
    assert month1["medicated"] and any("Saliparni" in m["text"] for m in month1["medicated"])
    assert foodguide.traditional(8, None)["procedures"]


def test_traditional_entries_respect_the_diet() -> None:
    meat = [f for f in foodguide.traditional(4, "non_vegetarian")["foods"] if "meat" in f["text"].lower()]
    assert meat
    assert not [f for f in foodguide.traditional(4, "vegetarian")["foods"] if "meat" in f["text"].lower()]
    assert foodguide.traditional(4, "vegetarian")["skipped_for_diet"] == 1
    vegan = foodguide.traditional(1, "vegan")["foods"]
    assert not [f for f in vegan if "milk" in f["text"].lower()]


def test_a_vegetarian_is_never_offered_meat_fish_egg_or_liver_and_allergies_are_respected() -> None:
    for need in foodguide.guide()["needs"]:
        rows = foodguide.modern(need, "vegetarian", ["almonds"])["foods"]
        names = " ".join(r["name"].lower() for r in rows)
        assert not any(w in names for w in ("chicken", "carp", "salmon", "sardine", "egg", "liver", "almond")), (need, names)
    vegan = foodguide.modern("calcium", "vegan", [])["foods"]
    assert all(r["category"] not in {"dairy_egg", "meat_fish"} for r in vegan)
    assert all("liver" not in f["name"].lower() for f in foodguide.modern("vitamin_a", None, [])["foods"])


def test_modern_values_come_from_the_usda_table_per_everyday_serving() -> None:
    by_name = {f["name"]: f for f in foods().values()}
    for row in foodguide.modern("iron", None, [])["foods"]:
        food = by_name[row["name"]]
        assert row["amount"] == pytest.approx(food["per_100g"]["iron"] * row["serving_g"] / 100, abs=0.06)
    ranked = [r["amount"] for r in foodguide.modern("protein", None, [])["foods"]]
    assert ranked == sorted(ranked, reverse=True)


def test_dry_grains_use_a_dry_serving_not_a_cooked_one() -> None:
    rows = {r["name"]: r for r in foodguide.modern("iron", None, [])["foods"] + foodguide.modern("protein", None, [])["foods"]}
    for name, row in rows.items():
        if name.startswith(("Amaranth grain", "Oats")):
            assert row["serving_g"] <= 50


def test_no_plant_food_is_offered_for_b12_to_a_vegan() -> None:
    result = foodguide.modern("vitamin_b12", "vegan", [])
    assert result["foods"] == [] and "ask your doctor" in result["empty_note"]
    assert "ask your doctor" in result["need"]["tip"].lower()


def test_unknown_need_is_rejected() -> None:
    with pytest.raises(KeyError):
        foodguide.modern("magic", None, [])


def test_the_foods_to_avoid_come_from_the_guard_rails_with_sources() -> None:
    items = foodguide.avoid_foods()
    assert len(items) >= 15
    assert all(i["why"] and i["sources"][0]["url"].startswith("https://") for i in items)
    assert any("raw" in i["name"].lower() for i in items)


def test_the_books_own_avoid_list_notes_where_modern_guidance_differs() -> None:
    harita = next(i for i in foodguide.guide()["avoid"]["items"] if i["authority"] == "Harita")
    assert "pulses" in harita["text"].lower() and "ICMR-NIN" in harita["modern"]


# ---- the endpoint ----------------------------------------------------------------------------------------------------


def _profile(client: TestClient, headers: dict[str, str], diet: str = "vegetarian", allergies: list[str] | None = None) -> None:
    body = {"consent": True, "consent_version": "v1.0", "diet_type": diet, "allergies": allergies or []}
    assert client.put("/profile", headers=headers, json=body).status_code == 200


def test_endpoint_needs_login(client: TestClient) -> None:
    assert client.get("/care/food-guide").status_code in {401, 403}


def test_endpoint_uses_the_week_the_diet_and_the_allergies(client: TestClient, auth_headers: dict[str, str]) -> None:
    _profile(client, auth_headers, "vegetarian", ["peanuts"])
    assert client.put("/care/dating", headers=auth_headers, json={"current_week": 21}).status_code == 200
    body = client.get("/care/food-guide?need=protein", headers=auth_headers).json()
    assert body["month"] == 5 and body["week"] == 21 and body["diet"] == "vegetarian"
    assert body["traditional"]["evidence_level"] == "traditional"
    assert body["traditional"]["book"]["scan_pages"]
    assert all("meat" not in f["text"].lower() for f in body["traditional"]["foods"])
    names = " ".join(f["name"].lower() for f in body["modern"]["foods"])
    assert "peanut" not in names and "chicken" not in names
    assert body["modern"]["need"]["daily_allowance"] == 71
    assert len(body["modern"]["needs"]) == 10
    assert any("medicines" in n for n in body["notes"])


def test_endpoint_lets_you_choose_a_month_and_rejects_bad_input(client: TestClient, auth_headers: dict[str, str]) -> None:
    _profile(client, auth_headers)
    body = client.get("/care/food-guide?month=2", headers=auth_headers).json()
    assert body["month"] == 2 and body["modern"]["need"] is None and body["traditional"]["medicated"]
    assert client.get("/care/food-guide?need=magic", headers=auth_headers).status_code == 422
    assert client.get("/care/food-guide?month=12", headers=auth_headers).status_code == 422


def test_without_a_week_the_endpoint_still_answers_and_asks_for_a_month(client: TestClient, auth_headers: dict[str, str]) -> None:
    body = client.get("/care/food-guide", headers=auth_headers).json()
    assert body["month"] is None and body["traditional"]["foods"] == []
    assert body["traditional"]["months_available"] == list(range(1, 10))


def test_the_book_guide_file_parses_as_yaml_with_every_need_defined() -> None:
    needs = yaml.safe_load((REPO / "backend" / "app" / "data" / "food_guide.yaml").read_text())["needs"]
    from app.services.care.rules import rules

    allowance = rules()["nutrition_targets"]["per_day"]
    for key, spec in needs.items():
        assert spec["label"] and spec["unit"], key
        assert spec["nutrient"] in allowance or spec.get("target"), key


# ---- allergies (issue #93) ----------------------------------------------------------------------------------------------

from app.services.care import allergens  # noqa: E402
from app.services.care.meals import gaps  # noqa: E402

# allergy as a person types it -> words that must never appear in a suggested food
ALLERGY_CASES = {
    "dairy": ["milk", "yogurt", "cottage cheese", "ghee"],
    "lactose": ["milk", "yogurt", "cottage cheese", "ghee"],
    "milk products": ["milk", "yogurt", "cottage cheese", "ghee"],
    "fish": ["carp", "salmon", "sardine"],
    "tree nuts": ["almond", "walnut", "cashew", "pistachio"],
    "nuts": ["almond", "walnut", "cashew", "pistachio", "peanut"],
    "peanut": ["peanut"],
    "gluten": ["wheat", "bread", "oats"],
    "wheat": ["wheat", "bread"],
    "soya": ["soybean", "tofu"],
    "sesame": ["sesame"],
    "egg": ["egg (hard"],
    "lentils": ["lentil"],
    "I am allergic to milk": ["milk", "yogurt"],
}


@pytest.mark.parametrize("allergy", list(ALLERGY_CASES))
def test_category_allergies_remove_every_food_in_the_category(allergy: str) -> None:
    for need in foodguide.guide()["needs"]:
        names = " | ".join(r["name"].lower() for r in foodguide.modern(need, None, [allergy])["foods"])
        for word in ALLERGY_CASES[allergy]:
            assert word not in names, (allergy, need, word, names)


def test_allergies_match_whole_words_so_egg_keeps_eggplant_and_pea_keeps_chickpeas() -> None:
    by_name = {f["name"]: f for f in foods().values()}
    assert allergens.food_blocked(by_name["Egg (hard-boiled)"], allergens.resolve(["egg"]))
    assert not allergens.food_blocked(by_name["Eggplant (baingan, cooked)"], allergens.resolve(["egg"]))
    assert allergens.food_blocked(by_name["Green peas (matar, cooked)"], allergens.resolve(["pea"]))
    assert not allergens.food_blocked(by_name["Chickpeas (chana)"], allergens.resolve(["pea"]))
    assert not allergens.food_blocked(by_name["Almonds (badam)"], allergens.resolve(["peanut"]))
    assert not allergens.food_blocked(by_name["Peanuts (moongphali, dry-roasted)"], allergens.resolve(["tree nuts"]))


def test_a_single_food_allergy_is_matched_directly() -> None:
    assert "mango" not in " ".join(r["name"].lower() for r in foodguide.modern("vitamin_c", None, ["mango"])["foods"])


def test_an_allergy_that_cannot_be_matched_is_reported_not_ignored() -> None:
    notes = foodguide.modern("protein", None, ["xyzzy"])["allergy_notes"]
    assert notes and "xyzzy" in notes[0] and "check each food yourself" in notes[0]
    assert foodguide.modern("protein", None, ["dairy"])["allergy_notes"] == ["Left out because of your allergies: milk and dairy."]
    assert foodguide.modern("protein", None, [])["allergy_notes"] == []


def test_the_books_regimen_respects_allergies_too() -> None:
    assert any("milk" in f["text"].lower() for f in foodguide.traditional(1, None, [])["foods"])
    t = foodguide.traditional(1, None, ["milk"])
    assert not any(w in f["text"].lower() for f in t["foods"] for w in ("milk", "ghrta", "butter"))
    assert t["skipped_for_allergy"] >= 1
    # honey, meat and cereals are covered as well
    assert not any("honey" in f["text"].lower() for f in foodguide.traditional(3, None, ["honey"])["foods"])
    assert not any("meat" in f["text"].lower() for f in foodguide.traditional(4, None, ["meat"])["foods"])
    assert not any("cereals" in f["text"].lower() for f in foodguide.traditional(9, None, ["gluten"])["foods"])


def test_meal_suggestions_respect_allergies_the_same_way() -> None:
    rows = gaps({}, None, ["dairy", "fish"])["suggestions"]
    offered = " | ".join(f["name"].lower() for s in rows for f in s["foods"])
    assert offered and not any(w in offered for w in ("milk", "yogurt", "cheese", "ghee", "carp", "salmon", "sardine"))


def test_the_endpoint_applies_a_dairy_allergy_from_the_profile(client: TestClient, auth_headers: dict[str, str]) -> None:
    _profile(client, auth_headers, "non_vegetarian", ["dairy"])
    client.put("/care/dating", headers=auth_headers, json={"current_week": 2})  # month 1 has a milk entry
    body = client.get("/care/food-guide?need=calcium", headers=auth_headers).json()
    names = " ".join(f["name"].lower() for f in body["modern"]["foods"])
    assert "milk" not in names and "yogurt" not in names and "ghee" not in names
    assert not any("milk" in f["text"].lower() for f in body["traditional"]["foods"])
    assert body["traditional"]["skipped_for_allergy"] >= 1
    assert any("milk and dairy" in n for n in body["modern"]["allergy_notes"])
