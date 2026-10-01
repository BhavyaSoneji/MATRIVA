# Glossary

## Ayurvedic and book terms

The spellings follow the *Prasuti Tantra* (Prof. Premvati Tiwari), which transliterates Sanskrit its own way. The meanings are the book's, in brief. They are traditional terms, not modern clinical ones.

| Term | Meaning |
|---|---|
| **Garbha** | The embryo or fetus; also the pregnancy |
| **Garbhini** | A pregnant woman |
| **Garbhini paricharya** | Antenatal care: the regimen and conduct advised for a pregnant woman |
| **Pathya** / **apathya** | Wholesome, suitable food and conduct / unsuitable ones |
| **Masanumasika pathya** | The *month-wise* dietary regimen: what to take in each month of pregnancy (the basis of `/foods`) |
| **Madhura group** | Drugs and foods classed as sweet in taste and nourishing. Herbs from this group are used to prepare medicated milk and ghee, which the food guide lists only as "treatments the book describes" |
| **Kshira** | Milk. The book advises milk through the whole of pregnancy ("milk is a whole diet") |
| **Ghrta** | Ghee. *Ghrta extracted from milk* is ghee made from the butter of milk |
| **Navanita** | Butter |
| **Sasti rice** (*shashtika*) | A rice said to ripen in sixty days; cooked with milk or curd in months 3 to 5 |
| **Yavagu** | Thin rice gruel, often with milk and ghee |
| **Payasa** | Rice cooked in milk and sweetened |
| **Krsara** | A preparation of rice and pulse |
| **Jangala mamsa** | Meat of wild, dry-land animals; *meat-soup* is advised in later months by some authorities. Hidden for vegetarian and vegan diets |
| **Aksa** | A traditional unit of weight; the book gives one aksa as 2 tola |
| **Basti** | A medicated enema. *Anuvasana* uses oil, *asthapana* a decoction. Described for months 8 and 9; never advised here |
| **Dauhrda** | The "two hearts": cravings of a pregnant woman, which the book discusses at length |
| **Sutika** | A woman after childbirth; *sutika paricharya* is postnatal care |
| **Stanya** | Breast milk; **dhatri** is a wet nurse |
| **Vata, pitta, kapha** | The three *doshas*, the body's functional principles in Ayurveda. The book explains many pregnancy symptoms through them |
| **Pesi** | A stage of the embryo's development in the book's month-by-month account |

### Authorities cited in the book

| Name | Work |
|---|---|
| **Caraka** | *Caraka Samhita* |
| **Susruta** | *Susruta Samhita* |
| **Vagbhata I and II** | *Astanga Sangraha* and *Astanga Hrdaya* |
| **Kasyapa** | *Kasyapa Samhita* |
| **Bhela** | *Bhela Samhita* |
| **Harita** | *Harita Samhita* |
| **Bhavamisra** | *Bhavaprakasa* |
| **Yogaratnakara** | *Yogaratnakara* |
| **Dalhana, Cakrapani, Indu, Arunadatta** | Commentators the book also cites |

The book names 16 authorities in all; the counts per chapter are in `backend/app/data/book_index.json` and in the `/book` card.

## Clinical and programme terms

| Term | Meaning |
|---|---|
| **ANC** | Antenatal care: the scheduled check-ups during pregnancy |
| **ANM**, **ASHA** | Auxiliary Nurse Midwife and Accredited Social Health Activist: the community health workers a mother is most likely to meet |
| **PMSMA** | Pradhan Mantri Surakshit Matritva Abhiyan: a free check-up with a doctor on the 9th of every month at government facilities |
| **JSSK**, **JSY** | Janani Shishu Suraksha Karyakram (free care and delivery in government facilities) and Janani Suraksha Yojana |
| **FOGSI** | Federation of Obstetric and Gynaecological Societies of India |
| **ICMR-NIN** | Indian Council of Medical Research, National Institute of Nutrition: the source of India's dietary guidelines |
| **IFA** | Iron and folic acid tablets given through the government programme |
| **MTP Act** | Medical Termination of Pregnancy Act, 1971, amended 2021 |
| **PCPNDT Act** | Pre-Conception and Pre-Natal Diagnostic Techniques Act, 1994: bars finding out or telling the sex of an unborn baby |
| **DPDP Act** | Digital Personal Data Protection Act, 2023 |
| **LMP**, **EDD** | Last menstrual period, estimated due date |
| **Trimester** | Weeks 1 to 13, 14 to 27, 28 to 40 |
| **Hb** | Haemoglobin; below 11 g/dL in pregnancy is anaemia (WHO) |
| **Pre-eclampsia** | High blood pressure with other signs (headache, vision changes, swelling) after 20 weeks; an emergency |
| **GDM**, **OGTT** | Gestational diabetes; the oral glucose tolerance test used to find it |
| **Rh-negative**, **anti-D** | A blood group that can need an anti-D injection after bleeding, a fall or delivery |
| **Tele-MANAS** | The national mental-health helpline, 14416 |
| **IFCT**, **USDA FDC** | Indian Food Composition Tables; USDA FoodData Central, the nutrient source the app uses |

## How the software describes itself

| Term | Meaning |
|---|---|
| **RAG** | Retrieval-augmented generation: find passages first, then answer from them |
| **Offline engine** | MATRIVA's default RAG: no language model, no API, no network. It quotes approved passages |
| **Approved / pending** | A document answers questions only once an admin approves it. Everything loads as pending |
| **Extractive composer** | Builds the answer from real sentences of the passages, so it cannot add a claim |
| **Sufficiency gate** | The check that decides the evidence is strong enough to answer at all; otherwise "I don't have a reviewed source" |
| **BM25** | Word-matching score used for retrieval |
| **Character n-grams** | Matching on pieces of words, which tolerates spelling and OCR damage |
| **LSA** | Latent semantic analysis: finds passages with the same meaning in different words |
| **RRF** | Reciprocal rank fusion: merges several rankings into one |
| **MMR** | Maximal marginal relevance: keeps results varied |
| **PRF** | Pseudo-relevance feedback: widens a search with terms from its best hits |
| **Guard rail** | One rule in the safety layer: a trigger, an action (escalate, block, caution), a message and sources |
| **Escalate / block / caution** | Emergency message only / refuse and refer / answer with a notice in front |
| **Fail closed** | If a safety component breaks, refuse instead of guessing |
| **Held-out set** | Test questions written after tuning and never tuned on |
| **Ablation** | Switching one signal off to measure what it was worth |
| **hit@k, MRR** | How often the right document is in the top k results; mean reciprocal rank |
