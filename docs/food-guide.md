# What to eat

`/foods` in the chat (or **What to eat** in the sidebar) shows two things, kept apart and labelled:

1. **From the book: the month-wise dietary regimen of the Prasuti Tantra** (Prof. Premvati Tiwari, chapter 5), for the month of pregnancy you are in. Each entry is the book's own English wording, the authority it is attributed to (Caraka, Susruta, Vagbhata, Bhela, Harita) and the scanned page. This is **traditional (Ayurvedic) knowledge, not modern clinical evidence.**
2. **Foods rich in a nutrient**, for the nutrient you pick: iron, calcium, protein, folate, vitamin C, vitamin B12, zinc, magnesium, vitamin A or fibre. Foods are ranked by how much one everyday serving gives, from the USDA table already used by the meal log, next to the NIH pregnancy allowance.

It also lists foods and habits to avoid or limit (the same rules the chat's guard rails use, with their sources) and what the book itself lists as unsuitable, saying where modern guidance differs.

**Foods only.** MATRIVA does not advise on medicines, tablets or herbal products. The book also describes milk, ghee or rice prepared with named herbs, and enemas. These are shown in a separate, collapsed "treatments the book also describes (not food, not advice)" section, never as food, with a note to ask your doctor and an Ayurvedic physician. Iron and folic acid tablets are for your ANM or doctor.

## The book's regimen, by month

| Month | The book says (foods only) |
|---|---|
| 1 | Non-medicated milk as desired; a sweet, cold, liquid, congenial diet, morning and evening |
| 2 | Sweet, cold, liquid diet |
| 3 | Milk with honey and ghee; cooked *sasti* rice with milk; *krsara* (rice and pulse) |
| 4 | Milk with butter; *sasti* rice with curd, milk and butter (and meat of wild animals, per Susruta) |
| 5 | Ghee from milk; rice cooked with milk; *yavagu* (rice gruel); *payasa* |
| 6 | Ghee prepared from milk; sweetened curd |
| 7 | Sweet preparation of ghee (*ghrtakhanda*) |
| 8 | Rice gruel with milk and ghee; liquid diet with ghee and milk; unctuous gruels (and meat-soup per Susruta) |
| 9 | Rice gruel with plenty of fat; different varieties of cereals; meat-soup with rice (per Vagbhata II) |

Entries with meat are hidden for vegetarian and vegan diets, and entries with milk or ghee are hidden for vegan diets; the card says how many were left out. Month comes from your week (week ÷ 4.345, up to 9) and can be changed on the card.

The book gives its own reasons (scanned pages 139-140): cold sweet liquid diet and milk in the first trimester when nausea makes eating hard; more protein from the fourth month; a diuretic herb in the sixth month for swelling; an enema in the eighth for constipation. The card shows them as the book's reasoning, not as modern evidence.

## How it is built

| | |
|---|---|
| Data | `backend/app/data/food_guide.yaml`: the regimen (37 entries, each with authority, kind, diet tags, scanned page), the book's reasoning, the foods it lists as unsuitable, and the 10 nutrient needs |
| Service | `backend/app/services/care/foodguide.py` |
| API | `GET /care/food-guide?need=iron&month=5` (login required; week, diet and allergies come from your profile) |
| Card | `frontend/components/care/foods-widget.tsx` |
| Nutrient values | `backend/app/data/foods_nutrients.json` (USDA FoodData Central), allowances in `care_rules.yaml` (NIH ODS) |

Each entry is `kind: food`, `medicated` (prepared with named herbs) or `procedure` (an enema). Only `food` is ever shown as food. `paraphrased: true` marks an entry whose wording was restated because the scan was damaged.

## What stops it giving bad suggestions

- A test checks that every quoted entry really appears in the OCR text of the book, so nothing is invented. Four entries were restated because of OCR damage and are marked.
- A vegetarian is never offered meat, fish, egg or liver; a vegan is never offered dairy or egg; a listed allergy removes the food. Liver is never suggested (very high in preformed vitamin A).
- No plant food reliably gives vitamin B12, so a vegan who asks for it is told so and sent to a doctor, not given a list.
- Dry grains and seeds use a realistic dry serving (for example 50 g of oats, 15 g of seeds), not the cooked 150 g that would make them look far richer than they are.
- The book's list of unsuitable foods includes pulses, garlic and onion (Harita). The card shows it with the note that ICMR-NIN recommends pulses and the NHS does not list pulses, garlic or onion as foods to avoid, and says to follow modern guidance and your doctor.

## Limits

- The book is a translation of classical texts through an imperfect scan. Four entries are restated, and a few Sanskrit terms (*sasti*, *aksa*, *madhura* group) are left as the book has them.
- Traditional advice is not tested by modern trials, and it has not been reviewed by a clinician. The nutrient values are approximate USDA values for a limited list of 67 foods, not a full Indian food table.
- It gives foods in general, not a diet plan. With diabetes, high blood pressure, anaemia, allergies or any condition, ask your doctor or a dietitian for your own plan; the chat's guard rails still apply to anything you ask about.
