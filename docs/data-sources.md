# Data sources

Every claim MATRIVA makes comes from one of the places below. Nothing here has been verified line by line by a clinician: each entry is a pointer to where the claim can be checked.

## 1. The knowledge base that answers questions

Only passages in **approved, active** documents can answer a question; everything is loaded as *pending* and approved by an admin.

| Source | What it gives |
|---|---|
| **Prasuti Tantra evam Stri Roga**, Prof. Premvati Tiwari (scan in `knowledge/ayurveda/`) | Classical Ayurvedic obstetrics, bilingual. 11 chapters, 567 English passages recovered from the OCR, a bilingual glossary, and the authorities cited per chapter |
| Public-health guidance, paraphrased (`knowledge/seed/guidelines.yaml`) | 26 entries from the authorities below, each with its primary-source URL |
| Seed documents (`knowledge/seed/seed.yaml`) | The FOGSI visit schedule, two Garbhini Paricharya entries, five IFCT food profiles |
| Foods (`knowledge/seed/foods.yaml`, built into `foods_nutrients.json`) | 67 USDA FoodData Central profiles for foods common in Indian diets |

Authorities in the guidance file:

| Authority | Entries | Examples |
|---|---:|---|
| NHS (UK) | 13 | [Foods to Avoid or Limit in Pregnancy](https://www.nhs.uk/pregnancy/keeping-well/foods-to-avoid/); [Folic Acid and Vitamin D in Pregnancy](https://www.nhs.uk/pregnancy/keeping-well/have-a-healthy-diet/); [Warning Signs of Pre-eclampsia](https://www.nhs.uk/conditions/pre-eclampsia/) … |
| World Health Organization | 6 | [Daily Iron and Folic Acid Supplementation in Pregnancy](https://www.who.int/publications/i/item/9789241549912); [Calcium Supplementation to Reduce Pre-eclampsia Risk](https://www.who.int/publications/i/item/9789241549912); [Limiting Caffeine in Pregnancy](https://www.who.int/publications/i/item/9789241549912) … |
| ICMR-National Institute of Nutrition, India | 5 | [Extra Food and Nutrients During Pregnancy](https://www.nin.res.in/downloads/DietaryGuidelinesforNINwebsite.pdf); [What to Eat in Pregnancy - a Balanced Indian Plate](https://www.nin.res.in/downloads/DietaryGuidelinesforNINwebsite.pdf); [Iron in Pregnancy - Foods, Absorption and Supplements](https://www.nin.res.in/downloads/DietaryGuidelinesforNINwebsite.pdf) … |
| Ministry of Health and Family Welfare, Government of India | 1 | [Pradhan Mantri Surakshit Matritva Abhiyan (PMSMA) - Free Mon](https://www.nhm.gov.in/index1.php?lang=1&level=2&sublinkid=822&lid=218) |
| Ministry of Women and Child Development, Government of India | 1 | [Pradhan Mantri Matru Vandana Yojana (PMMVY) - Maternity Cash](https://pmmvy.wcd.gov.in/) |

## 2. Care rules and nutrition

| Used for | Source |
|---|---|
| Visit calendar, PMSMA on the 9th | FOGSI; WHO antenatal-care model (2016); MoHFW |
| Haemoglobin, blood pressure, glucose flags | WHO; NICE NG133; NHS |
| Red-flag screening questions | NHS; WHO; FOGSI |
| Daily allowances (iron 27 mg, calcium 1000 mg, protein 71 g ...) | [NIH Office of Dietary Supplements](https://ods.od.nih.gov/) |
| Nutrient values per 100 g | [USDA FoodData Central](https://fdc.nal.usda.gov/) (SR Legacy) |
| Fibre allowance (28 g) | National Academies DRI |
| Indian dietary guidance | [ICMR-NIN Dietary Guidelines for Indians](https://www.nin.res.in/) |

All of `care_rules.yaml` is marked `pending_clinical_review`.

## 3. Guard rails

Each of the 1,231 rules lists keys from this table of 40 named sources (`backend/app/data/guardrails/sources.yaml`). A key means "this is the reference the rule is consistent with", not "this page says exactly this". Where a stable deep link was not certain, the link goes to the issuing body's site.

| Key | Source |
|---|---|
| nhs-medicines | [NHS - Medicines in pregnancy](https://www.nhs.uk/pregnancy/keeping-well/medicines/) |
| nhs-foods | [NHS - Foods to avoid in pregnancy](https://www.nhs.uk/pregnancy/keeping-well/foods-to-avoid/) |
| nhs-alcohol | [NHS - Alcohol in pregnancy](https://www.nhs.uk/pregnancy/keeping-well/alcohol-and-pregnancy/) |
| nhs-smoking | [NHS - Stop smoking in pregnancy](https://www.nhs.uk/pregnancy/keeping-well/stop-smoking/) |
| nhs-exercise | [NHS - Exercise in pregnancy](https://www.nhs.uk/pregnancy/keeping-well/exercise/) |
| nhs-movements | [NHS - Your baby's movements](https://www.nhs.uk/pregnancy/keeping-well/your-babys-movements/) |
| nhs-bleeding | [NHS - Vaginal bleeding in pregnancy](https://www.nhs.uk/pregnancy/related-conditions/common-symptoms/vaginal-bleeding/) |
| nhs-preeclampsia | [NHS - Pre-eclampsia](https://www.nhs.uk/conditions/pre-eclampsia/) |
| nhs-gdm | [NHS - Gestational diabetes](https://www.nhs.uk/conditions/gestational-diabetes/) |
| nhs-cholestasis | [NHS - Obstetric cholestasis](https://www.nhs.uk/conditions/obstetric-cholestasis/) |
| nhs-dvt | [NHS - Deep vein thrombosis](https://www.nhs.uk/conditions/deep-vein-thrombosis-dvt/) |
| nhs-miscarriage | [NHS - Miscarriage](https://www.nhs.uk/conditions/miscarriage/) |
| nhs-ectopic | [NHS - Ectopic pregnancy](https://www.nhs.uk/conditions/ectopic-pregnancy/) |
| nhs-pregnancy | [NHS - Pregnancy](https://www.nhs.uk/pregnancy/) |
| nhs-labour | [NHS - Labour and birth](https://www.nhs.uk/pregnancy/labour-and-birth/) |
| nhs-travel | [NHS - Travelling in pregnancy](https://www.nhs.uk/pregnancy/keeping-well/travelling/) |
| fda-nsaid | [US FDA - Avoid NSAIDs at 20 weeks or later in pregnancy (2020)](https://www.fda.gov/drugs/drug-safety-and-availability/fda-recommends-avoiding-use-nsaids-pregnancy-20-weeks-or-later-because-they-can-result-problems) |
| fda-labeling | [US FDA - Pregnancy and lactation drug labelling](https://www.fda.gov/drugs/labeling-information-drug-products/pregnancy-and-lactation-labeling-drugs-final-rule) |
| fda-fish | [US FDA - Advice about eating fish](https://www.fda.gov/food/consumers/advice-about-eating-fish) |
| acog | [ACOG - Patient and clinical guidance](https://www.acog.org/) |
| cdc-pregnancy | [CDC - Pregnancy](https://www.cdc.gov/pregnancy/) |
| cdc-listeria | [CDC - Listeria](https://www.cdc.gov/listeria/) |
| mothertobaby | [MotherToBaby (OTIS) - Medication fact sheets](https://mothertobaby.org/fact-sheets/) |
| who-anc | [WHO - Recommendations on antenatal care for a positive pregnancy experience (2016)](https://www.who.int/publications/i/item/9789241549912) |
| who-alcohol | [WHO - Alcohol](https://www.who.int/health-topics/alcohol) |
| who-tobacco | [WHO - Tobacco](https://www.who.int/health-topics/tobacco) |
| nice-hypertension | [NICE NG133 - Hypertension in pregnancy](https://www.nice.org.uk/guidance/ng133) |
| rcog | [RCOG - Patient information and green-top guidelines](https://www.rcog.org.uk/) |
| fogsi | [FOGSI - Good clinical practice recommendations](https://www.fogsi.org/) |
| mohfw | [MoHFW (India) - Antenatal care and safe motherhood guidance](https://main.mohfw.gov.in/) |
| nhm | [National Health Mission - PMSMA, JSSK and maternal health](https://nhm.gov.in/) |
| icmr-nin | [ICMR-NIN - Dietary guidelines for Indians](https://www.nin.res.in/) |
| ayush | [Ministry of AYUSH](https://ayush.gov.in/) |
| mtp-act | [Medical Termination of Pregnancy Act, 1971 (amended 2021)](https://www.indiacode.nic.in/) |
| pcpndt | [Pre-Conception and Pre-Natal Diagnostic Techniques (PCPNDT) Act, 1994](https://www.indiacode.nic.in/) |
| tele-manas | [Tele-MANAS (Govt. of India mental-health helpline 14416)](https://telemanas.mohfw.gov.in/) |
| helpline-181 | [Women Helpline 181 (Ministry of Women and Child Development)](https://wcd.nic.in/) |
| erss-112 | [Emergency Response Support System 112](https://112.gov.in/) |
| cdc-vaccines | [CDC - Vaccines during pregnancy](https://www.cdc.gov/vaccines/pregnancy/) |
| nhs-vaccines | [NHS - Vaccinations in pregnancy](https://www.nhs.uk/pregnancy/keeping-well/vaccinations/) |

## 4. Videos, articles and papers

`backend/app/data/library.yaml` (built by `knowledge/resources/build_library.py`) holds about 85 curated videos, NHS, WHO, ACOG and Government of India pages, and PubMed papers. The links were checked when the list was built and are not re-checked while the app runs.

## 5. Helplines and legal facts used in messages

| Fact | Source |
|---|---|
| 112 national emergency, 102 ambulance for pregnant women and infants | [ERSS 112](https://112.gov.in/); National Health Mission |
| Tele-MANAS 14416 mental-health helpline | [Tele-MANAS](https://telemanas.mohfw.gov.in/) |
| Women Helpline 181 | Ministry of Women and Child Development |
| Abortion legal to 20 weeks on one registered doctor's opinion and to 24 weeks in listed situations | MTP Act 1971, amended 2021 |
| Sex determination of an unborn baby is illegal | PCPNDT Act 1994 |
| Free antenatal care and delivery in government facilities; PMSMA on the 9th | JSSK; PMSMA (National Health Mission) |

Helpline numbers and laws change. Re-check them before each release.
