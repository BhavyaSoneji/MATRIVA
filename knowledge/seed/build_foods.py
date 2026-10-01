"""Builds knowledge/seed/foods.yaml: nutrient profiles for foods common in Indian diets.

Source: USDA FoodData Central, SR Legacy (public domain). Every number in the output is
read straight from the dataset record named in `FOODS` -- nothing is typed from memory,
and the exact USDA description is written into each entry so a reviewer can look it up.

Each entry reports per-100 g values plus what share of the US pregnancy RDA (NIH Office
of Dietary Supplements) that is, so users can compare foods. It makes no health claims.
The USDA records are North-American samples; the entry says so, and points to IFCT 2017
for Indian-variety values.

Usage:  python knowledge/seed/build_foods.py
"""

from __future__ import annotations

import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

import yaml

DATASET_URL = "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_json_2018-04.zip"
OUT = Path(__file__).with_name("foods.yaml")

# nutrient number in SR Legacy -> (label, unit, decimals)
NUTRIENTS = {
    "208": ("energy", "kcal", 0),
    "203": ("protein", "g", 1),
    "291": ("fibre", "g", 1),
    "301": ("calcium", "mg", 0),
    "303": ("iron", "mg", 1),
    "304": ("magnesium", "mg", 0),
    "309": ("zinc", "mg", 1),
    "401": ("vitamin C", "mg", 1),
    "435": ("folate (DFE)", "mcg", 0),
    "418": ("vitamin B12", "mcg", 1),
    "320": ("vitamin A (RAE)", "mcg", 0),
}

# US RDA for pregnancy, adults 19-50 (NIH ODS). Used only to express "% of RDA per 100 g".
PREGNANCY_RDA = {"calcium": 1000, "iron": 27, "folate (DFE)": 600, "vitamin C": 85,
                 "vitamin B12": 2.6, "vitamin A (RAE)": 770, "zinc": 11, "magnesium": 350}

# (USDA description prefix, display name, subdomain, extra note or None)
FOODS = [
    ("Lentils, mature seeds, cooked, boiled, without salt", "Lentils (masoor dal)", "legumes", None),
    ("Chickpeas (garbanzo beans, bengal gram), mature seeds, cooked, boiled, without salt", "Chickpeas (chana)", "legumes", None),
    ("Mung beans, mature seeds, cooked, boiled, without salt", "Mung beans (moong)", "legumes", None),
    ("Pigeon peas (red gram), mature seeds, cooked, boiled, without salt", "Pigeon peas (toor / arhar dal)", "legumes", None),
    ("Beans, kidney, all types, mature seeds, cooked, boiled, without salt", "Kidney beans (rajma)", "legumes", None),
    ("Cowpeas, common (blackeyes, crowder, southern), mature seeds, cooked, boiled, without salt", "Cowpeas (lobia / chawli)", "legumes", None),
    ("Beans, black, mature seeds, cooked, boiled, without salt", "Black beans", "legumes", None),
    ("Soybeans, mature seeds, cooked, boiled, with salt", "Soybeans", "legumes", None),
    ("Tofu, raw, firm, prepared with calcium sulfate", "Tofu (firm)", "legumes", None),
    ("Millet, cooked", "Millet (cooked)", "grains_millets", "The USDA record is generic millet, not specifically ragi (finger millet) or bajra (pearl millet)."),
    ("Rice, brown, long-grain, cooked", "Brown rice (cooked)", "grains_millets", None),
    ("Rice, white, long-grain, regular, enriched, cooked", "White rice (cooked)", "grains_millets", None),
    ("Wheat flour, whole-grain", "Whole wheat flour (atta)", "grains_millets", None),
    ("Oats", "Oats", "grains_millets", None),
    ("Sorghum grain", "Sorghum (jowar)", "grains_millets", None),
    ("Amaranth grain, uncooked", "Amaranth grain (rajgira)", "grains_millets", None),
    ("Quinoa, cooked", "Quinoa (cooked)", "grains_millets", None),
    ("Bread, whole-wheat, commercially prepared", "Whole wheat bread", "grains_millets", None),
    ("Milk, reduced fat, fluid, 2% milkfat, with added vitamin A and vitamin D", "Milk (2% fat)", "dairy_eggs", None),
    ("Yogurt, plain, low fat", "Plain yogurt (dahi / curd)", "dairy_eggs", None),
    ("Cheese, cottage, lowfat, 2% milkfat", "Cottage cheese (low fat)", "dairy_eggs", "Cottage cheese is not the same food as paneer; values differ."),
    ("Butter oil, anhydrous", "Ghee (anhydrous butter oil)", "dairy_eggs", None),
    ("Egg, whole, cooked, hard-boiled", "Egg (hard-boiled)", "dairy_eggs", None),
    ("Chicken, broilers or fryers, breast, meat only, cooked, roasted", "Chicken breast (roasted)", "meat_fish", None),
    ("Chicken, liver, all classes, cooked, simmered", "Chicken liver (cooked)", "meat_fish",
     "NHS advises avoiding liver and liver products during pregnancy because they contain very high levels of vitamin A, which can harm the baby."),
    ("Fish, carp, cooked, dry heat", "Carp (cooked; rohu is a carp)", "meat_fish", None),
    ("Fish, salmon, Atlantic, farmed, cooked, dry heat", "Salmon (cooked)", "meat_fish",
     "Salmon is an oily fish; NHS advises no more than two portions of oily fish a week in pregnancy."),
    ("Fish, sardine, Atlantic, canned in oil, drained solids with bone", "Sardines (canned, with bone)", "meat_fish",
     "Sardines are an oily fish; NHS advises no more than two portions of oily fish a week in pregnancy."),
    ("Spinach, cooked, boiled, drained, without salt", "Spinach (palak, cooked)", "vegetables", None),
    ("Amaranth leaves, cooked, boiled, drained, without salt", "Amaranth leaves (chaulai, cooked)", "vegetables", None),
    ("Drumstick leaves, raw", "Drumstick leaves (moringa / sahjan)", "vegetables", None),
    ("Mustard greens, cooked, boiled, drained, without salt", "Mustard greens (sarson, cooked)", "vegetables", None),
    ("Carrots, raw", "Carrot (gajar)", "vegetables", None),
    ("Pumpkin, cooked, boiled, drained, without salt", "Pumpkin (kaddu, cooked)", "vegetables", None),
    ("Sweet potato, cooked, baked in skin, flesh, without salt", "Sweet potato (shakarkandi)", "vegetables", None),
    ("Beets, cooked, boiled, drained", "Beetroot (chukandar, cooked)", "vegetables", None),
    ("Cauliflower, cooked, boiled, drained, without salt", "Cauliflower (gobi, cooked)", "vegetables", None),
    ("Broccoli, cooked, boiled, drained, without salt", "Broccoli (cooked)", "vegetables", None),
    ("Okra, cooked, boiled, drained, without salt", "Okra (bhindi, cooked)", "vegetables", None),
    ("Tomatoes, red, ripe, raw, year round average", "Tomato (raw)", "vegetables", None),
    ("Cabbage, cooked, boiled, drained, without salt", "Cabbage (cooked)", "vegetables", None),
    ("Gourd, white-flowered (calabash), raw", "Bottle gourd (lauki / doodhi)", "vegetables", None),
    ("Peas, green, cooked, boiled, drained, without salt", "Green peas (matar, cooked)", "vegetables", None),
    ("Beans, snap, green, cooked, boiled, drained, without salt", "Green beans (cooked)", "vegetables", None),
    ("Eggplant, cooked, boiled, drained, without salt", "Eggplant (baingan, cooked)", "vegetables", None),
    ("Peppers, sweet, red, raw", "Red bell pepper (raw)", "vegetables", None),
    ("Potatoes, boiled, cooked in skin, flesh, without salt", "Potato (aloo, boiled)", "vegetables", None),
    ("Bananas, raw", "Banana (kela)", "fruits", None),
    ("Oranges, raw, all commercial varieties", "Orange (santra)", "fruits", None),
    ("Guavas, common, raw", "Guava (amrood)", "fruits", None),
    ("Mangos, raw", "Mango (aam)", "fruits", None),
    ("Papayas, raw", "Ripe papaya (papita)", "fruits", None),
    ("Pomegranates, raw", "Pomegranate (anar)", "fruits", None),
    ("Apples, raw, with skin", "Apple (seb)", "fruits", None),
    ("Dates, medjool", "Dates (khajoor, medjool)", "fruits", None),
    ("Figs, dried, uncooked", "Dried figs (anjeer)", "fruits", None),
    ("Raisins, dark, seedless", "Raisins (kishmish)", "fruits", None),
    ("Watermelon, raw", "Watermelon (tarbooz)", "fruits", None),
    ("Nuts, almonds", "Almonds (badam)", "nuts_seeds", None),
    ("Nuts, walnuts, english", "Walnuts (akhrot)", "nuts_seeds", None),
    ("Nuts, cashew nuts, raw", "Cashews (kaju)", "nuts_seeds", None),
    ("Nuts, pistachio nuts, raw", "Pistachios (pista)", "nuts_seeds", None),
    ("Peanuts, all types, dry-roasted, with salt", "Peanuts (moongphali, dry-roasted)", "nuts_seeds", None),
    ("Seeds, flaxseed", "Flaxseed (alsi)", "nuts_seeds", None),
    ("Seeds, sesame seeds, whole, dried", "Sesame seeds (til)", "nuts_seeds", None),
    ("Seeds, pumpkin and squash seed kernels, dried", "Pumpkin seeds (kaddu ke beej)", "nuts_seeds", None),
    ("Seeds, chia seeds, dried", "Chia seeds", "nuts_seeds", None),
]


def _load_foods() -> dict[str, dict]:
    print("downloading USDA SR Legacy (13 MB)...", file=sys.stderr)
    raw = urllib.request.urlopen(DATASET_URL, timeout=180).read()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".json"))
        data = json.loads(zf.read(name))["SRLegacyFoods"]
    return {f["description"]: f for f in data}


def _values(food: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for fn in food["foodNutrients"]:
        number = fn.get("nutrient", {}).get("number")
        if number in NUTRIENTS and "amount" in fn:
            out[number] = fn["amount"]
    return out


def _fmt(label: str, value: float, unit: str, decimals: int) -> str:
    text = f"{value:.{decimals}f}" if decimals else f"{round(value)}"
    return f"{label} {text} {unit}"


def _entry(food: dict, display: str, subdomain: str, note: str | None) -> dict:
    values = _values(food)
    facts = [_fmt(NUTRIENTS[n][0], values[n], NUTRIENTS[n][1], NUTRIENTS[n][2]) for n in NUTRIENTS if n in values]
    shares = []
    for n, (label, _unit, _d) in NUTRIENTS.items():
        if label in PREGNANCY_RDA and n in values:
            pct = values[n] / PREGNANCY_RDA[label] * 100
            if pct >= 10:
                shares.append(f"{label} {round(pct)}%")
    parts = [
        f"{display}: nutrient values per 100 g from USDA FoodData Central (SR Legacy record "
        f"\"{food['description']}\"): " + ", ".join(facts) + ".",
    ]
    if shares:
        parts.append(
            "Share of the US recommended daily allowance for pregnancy provided by 100 g: "
            + ", ".join(shares) + "."
        )
    if note:
        parts.append(note)
    parts.append(
        "These are laboratory values for US samples; Indian varieties and cooking methods differ "
        "(see IFCT 2017). Portion size and the rest of the day's diet matter more than any single food."
    )
    fdc = food["fdcId"]
    return {
        "document_id": f"food-usda-{fdc}",
        "title": f"{display} - Nutrient Profile (USDA)",
        "content": " ".join(parts),
        "domain": "NUTRITION",
        "subdomain": subdomain,
        "source_id": "usda-fdc-sr-legacy",
        "source_type": "nutrition_reference",
        "authority": "USDA FoodData Central (SR Legacy)",
        "url": f"https://fdc.nal.usda.gov/fdc-app.html#/food-details/{fdc}/nutrients",
        "publication_date": "2019",
        "version": "SR Legacy 2018-04",
        "language": "en",
        "region": None,
        "jurisdiction": "USA (USDA)",
        "pregnancy_stage": "all",
        "topic": "nutrient_profile",
        "evidence_level": "SUPPORTED",
        "review_status": "PENDING_SOURCE_VERIFICATION",
        "reviewed_by": None,
        "reviewed_at": None,
        "safety_tags": ["avoid_in_pregnancy"] if "liver" in display.lower() else [],
    }


def main() -> int:
    by_desc = _load_foods()
    entries, missing = [], []
    for prefix, display, subdomain, note in FOODS:
        match = by_desc.get(prefix) or next((f for d, f in by_desc.items() if d.startswith(prefix)), None)
        if match is None:
            missing.append(prefix)
            continue
        entries.append(_entry(match, display, subdomain, note))
    header = (
        "# Generated by build_foods.py from USDA FoodData Central (SR Legacy). Do not hand-edit numbers;\n"
        "# re-run the script. All entries are PENDING_SOURCE_VERIFICATION and load as pending.\n"
        "# Topic names avoid the substring 'anc' (see guidelines.yaml).\n\n"
    )
    OUT.write_text(header + yaml.safe_dump(entries, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    print(f"wrote {len(entries)} entries to {OUT}")
    for m in missing:
        print("MISSING:", m, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
