"""Builds backend/app/data/library.yaml from a hand-curated list of real resources.

Every entry is verified against the live source when this script runs, so the
published titles/publishers are never typed from memory:

  - videos:   YouTube oEmbed (title + channel); an entry that no longer
              resolves is dropped and reported.
  - articles: an HTTP GET must succeed and must not redirect to a 404 page.
              NHS pages that moved are stored under their final URL.
  - research: PubMed E-utilities (title, journal, year, PMID).

Only metadata is stored (title, publisher, link) plus a one-line `about` that
describes what the resource covers. No third-party text is copied. The library
is a pointer collection for the chat UI -- it is NOT part of the reviewed
medical knowledge base that grounds answers, which is why it needs no
clinical approval workflow.

Writes backend/app/data/library.yaml.

Usage:  python knowledge/resources/build_library.py
"""

from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

# Lives inside backend/ so the Docker image (build context = backend/) ships it.
OUT = Path(__file__).resolve().parents[2] / "backend" / "app" / "data" / "library.yaml"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/605 Safari/605", "Accept-Language": "en"}

# (youtube_id, topic, stages, language, about)
VIDEOS = [
    ("wHBREuBXt4A", "nutrition", "all", "en", "Quick guide to nutrient-dense foods that support a healthy pregnancy."),
    ("4JirNGrwzDE", "nutrition", "all", "en", "Common things to avoid during pregnancy, from Mayo Clinic's pregnancy guide."),
    ("k6pvKOMmDkA", "nutrition", "all", "en", "How much weight gain is considered normal, and why it varies."),
    ("N_PglaMSA2k", "nutrition", "1", "en", "A nutritionist's first-trimester eating plan."),
    ("EAPOszWSbzY", "nutrition", "all", "en", "Eating well with gestational diabetes, with Indian meal ideas."),
    ("68NMhivpmWQ", "nutrition", "all", "en", "NHS dietitian advice for healthy eating with gestational diabetes."),
    ("T1RqEos_IO0", "nutrition", "all", "hi", "Foods that help with anaemia (low haemoglobin) in pregnancy, in Hindi."),
    ("bEi1i6V7dxA", "nutrition", "1", "en", "First-trimester precautions and do's and don'ts from an obstetrician."),
    ("8KJJD6Accsg", "lifestyle", "3", "en", "NHS: what you can do during pregnancy to make birth easier."),
    ("LMiNq_ai1hU", "lifestyle", "all", "en", "NHS: how and when to do pelvic floor exercises."),
    ("vfpkYRyt7mU", "lifestyle", "all", "en", "Short overview of exercising safely during pregnancy."),
    ("k0IpDleipkc", "lifestyle", "all", "en", "Mayo Clinic Minute on sex and exercise during pregnancy."),
    ("-3bvlFKeLRE", "lifestyle", "all", "en", "A gentle 22-minute prenatal yoga practice you can follow along with."),
    ("44fYnoSLL3c", "lifestyle", "all", "en", "Follow-along prenatal yoga routine led by actor Lara Dutta."),
    ("4NwQKXpWN_A", "lifestyle", "all", "en", "Ten-minute prenatal yoga for beginners, positioned as safe for all trimesters."),
    ("538yUiAg4no", "lifestyle", "2,3", "en", "Safe, comfortable sleeping positions in pregnancy from a maternity hospital."),
    ("J7OE3IWYoJE", "lifestyle", "2,3", "en", "Which sleeping position is best in pregnancy, explained by an obstetrician."),
    ("djc4jODdjbc", "symptoms", "1", "en", "A doctor explains how to manage nausea and vomiting in pregnancy."),
    ("Rx1qwCGi-vA", "symptoms", "1", "en", "Five remedies for pregnancy nausea and vomiting from a Cloudnine doctor."),
    ("xyfGRDkqIVQ", "safety", "2,3", "en", "NHS: what pre-eclampsia is and the warning signs to watch for."),
    ("bO1mnCMCGSM", "safety", "all", "en", "Pregnancy warning signs and when to call your doctor."),
    ("pBUXzJURch4", "safety", "3", "en", "How to count fetal movements (kick counts) and what to do if they change."),
    ("Z8zu88KZoUM", "schemes", "all", "en", "MyGov explainer on the PMSMA free monthly antenatal check-up scheme."),
    ("UtSplyUgw30", "schemes", "all", "en", "National Health Portal video on Pradhan Mantri Surakshit Matritva Abhiyan."),
    ("a2OtNC8Qbas", "schemes", "all", "en", "PIB short video on the Pradhan Mantri Surakshit Matritva Abhiyan."),
    ("QovJbtlz5jE", "mental", "all", "en", "Coping with anxiety and depression during pregnancy."),
    ("Rpbmzm6FeMM", "mental", "all", "en", "Hospital webinar on perinatal depression and anxiety (long-form)."),
    ("dwkCQNp25tA", "labour", "3", "en", "Signs of labour and when to reach the hospital."),
    ("1BFtfuiBLcw", "postnatal", "postpartum", "en", "Postpartum care 101 for new mothers."),
    ("Ai57c9QY2Ss", "postnatal", "3", "en", "How to prepare for breastfeeding during pregnancy."),
    ("6qOXeck_zNY", "postnatal", "postpartum", "en", "Recovery after a normal delivery: do's and don'ts."),
    ("6DiB-17rSFs", "ayurveda", "2", "en", "Masanumasika pathya (month-wise regimen) for months 4 and 5, from an Ayurveda hospital."),
    ("J8NLl4OqZa4", "ayurveda", "1", "en", "Early-pregnancy care from an Ayurveda hospital physician."),
    ("orWfzZMwNfc", "ayurveda", "all", "en", "Nine-month Ayurvedic diet plan (Garbhini Paricharya) overview."),
    ("KCIztM7wZY0", "ayurveda", "all", "en", "Long-form talk on the Ayurvedic approach to pregnancy and postpartum."),
    ("biaPb2LtRRc", "ayurveda", "all", "en", "Garbhsanskar: myths, diet and conception discussed by an Ayurveda doctor."),
    ("8BH7WFmRs-E", "development", "all", "en", "3D animation of pregnancy month by month."),
    ("rJSH6Iy_R-M", "development", "1", "en", "First-trimester fetal development, week by week."),
    ("t3VDyFOTdwU", "development", "1", "en", "Mayo Clinic talk on keeping yourself and baby healthy in early pregnancy."),
]

# (topic, stages, about, url)
ARTICLES = [
    ("nutrition", "all", "Official NHS list of foods to avoid or limit in pregnancy, and why.", "https://www.nhs.uk/pregnancy/keeping-well/foods-to-avoid/"),
    ("nutrition", "all", "NHS guide to a healthy pregnancy diet.", "https://www.nhs.uk/pregnancy/keeping-well/have-a-healthy-diet/"),
    ("nutrition", "all", "WHO fact sheet on anaemia: causes, prevention and why pregnancy raises the risk.", "https://www.who.int/news-room/fact-sheets/detail/anaemia"),
    ("nutrition", "all", "India's national nutrition mission (Poshan Abhiyaan), including support for pregnant women.", "https://poshanabhiyaan.gov.in/"),
    ("nutrition", "all", "ICMR-NIN Dietary Guidelines for Indians (PDF), with pregnancy-specific advice.", "https://www.nin.res.in/downloads/DietaryGuidelinesforNINwebsite.pdf"),
    ("nutrition", "all", "ACOG patient guide to gestational diabetes.", "https://www.acog.org/womens-health/faqs/gestational-diabetes"),
    ("safety", "all", "NHS overview of gestational diabetes: tests, treatment and diet.", "https://www.nhs.uk/conditions/gestational-diabetes/"),
    ("lifestyle", "all", "NHS guidance on exercising during pregnancy.", "https://www.nhs.uk/pregnancy/keeping-well/exercise/"),
    ("lifestyle", "all", "ACOG patient guide to exercise during pregnancy.", "https://www.acog.org/womens-health/faqs/exercise-during-pregnancy"),
    ("lifestyle", "all", "WHO fact sheet on physical activity, including recommendations for pregnant women.", "https://www.who.int/news-room/fact-sheets/detail/physical-activity"),
    ("lifestyle", "all", "NHS guidance on stopping smoking in pregnancy.", "https://www.nhs.uk/pregnancy/keeping-well/stop-smoking/"),
    ("lifestyle", "all", "NHS guidance on vaccinations recommended in pregnancy.", "https://www.nhs.uk/pregnancy/keeping-well/vaccinations/"),
    ("symptoms", "1", "NHS guide to morning sickness and when it needs medical help.", "https://www.nhs.uk/pregnancy/related-conditions/common-symptoms/vomiting-and-morning-sickness/"),
    ("symptoms", "2,3", "NHS advice on back pain in pregnancy.", "https://www.nhs.uk/pregnancy/related-conditions/common-symptoms/back-pain/"),
    ("safety", "2,3", "NHS: pre-eclampsia symptoms, diagnosis and treatment.", "https://www.nhs.uk/conditions/pre-eclampsia/"),
    ("safety", "2,3", "ACOG patient guide to pre-eclampsia and high blood pressure in pregnancy.", "https://www.acog.org/womens-health/faqs/preeclampsia-and-high-blood-pressure-during-pregnancy"),
    ("safety", "3", "NHS: your baby's movements and when reduced movement needs urgent attention.", "https://www.nhs.uk/pregnancy/keeping-well/your-babys-movements/"),
    ("safety", "all", "NHS overview of pregnancy complications.", "https://www.nhs.uk/pregnancy/complications/"),
    ("safety", "all", "WHO fact sheet on maternal mortality and its main preventable causes.", "https://www.who.int/news-room/fact-sheets/detail/maternal-mortality"),
    ("antenatal", "all", "WHO recommendations on antenatal care for a positive pregnancy experience (the 8-contact model).", "https://www.who.int/publications/i/item/9789241549912"),
    ("antenatal", "all", "NHS: what your antenatal appointments involve.", "https://www.nhs.uk/pregnancy/your-pregnancy-care/your-antenatal-care-and-appointments/"),
    ("schemes", "all", "Pradhan Mantri Matru Vandana Yojana: cash maternity benefit scheme.", "https://pmmvy.wcd.gov.in/"),
    ("schemes", "all", "National Health Mission page on maternal health programmes in India.", "https://www.nhm.gov.in/index1.php?lang=1&level=2&sublinkid=822&lid=218"),
    ("mental", "all", "NHS: mental health in pregnancy and where to find help.", "https://www.nhs.uk/pregnancy/mental-health-in-pregnancy-and-after-the-birth/mental-health/"),
    ("mental", "postpartum", "NHS: postnatal depression symptoms and treatment.", "https://www.nhs.uk/mental-health/conditions/postnatal-depression/"),
    ("mental", "postpartum", "ACOG patient guide to postpartum depression.", "https://www.acog.org/womens-health/faqs/postpartum-depression"),
    ("labour", "3", "NHS: signs that labour has begun.", "https://www.nhs.uk/pregnancy/labour-and-birth/signs-that-labour-has-begun/"),
    ("labour", "3", "NHS: the stages of labour and birth.", "https://www.nhs.uk/pregnancy/labour-and-birth/the-stages-of-labour-and-birth/"),
    ("labour", "3", "NHS labour and birth hub.", "https://www.nhs.uk/pregnancy/labour-and-birth/"),
    ("postnatal", "postpartum", "NHS guide to breastfeeding.", "https://www.nhs.uk/baby/breastfeeding-and-bottle-feeding/breastfeeding/"),
    ("postnatal", "postpartum", "WHO fact sheet on breastfeeding.", "https://www.who.int/news-room/fact-sheets/detail/breastfeeding"),
    ("postnatal", "postpartum", "WHO recommendations on maternal and newborn care for a positive postnatal experience.", "https://www.who.int/publications/i/item/9789240045989"),
    ("ayurveda", "all", "Ministry of Ayush: the Government of India's AYUSH systems of medicine portal.", "https://ayush.gov.in/"),
    ("ayurveda", "all", "WHO guidelines on research and evaluation of traditional medicine.", "https://www.who.int/publications/i/item/9789241506090"),
    ("development", "all", "NHS week-by-week guide to pregnancy.", "https://www.nhs.uk/best-start-in-life/pregnancy/week-by-week-guide-to-pregnancy/"),
]

# (pmid, topic, stages, about)
RESEARCH = [
    ("22557296", "ayurveda", "all", "Overview of the classical Ayurvedic regimen for the pregnant woman (Garbhini Paricharya)."),
    ("32619201", "ayurveda", "all", "Review of Ayurveda in early life and non-communicable disease prevention."),
    ("35337282", "lifestyle", "all", "Meta-analysis of pregnancy yoga interventions and their effectiveness."),
    ("32446148", "lifestyle", "all", "Systematic review of the effects of yoga on pregnancy."),
    ("36156844", "lifestyle", "all", "Umbrella review: exercise in pregnancy and gestational diabetes / hypertensive disorders."),
    ("30337463", "lifestyle", "all", "Meta-analysis: prenatal exercise and prevention of gestational diabetes."),
    ("24642205", "symptoms", "1", "Meta-analysis of the safety and effect of ginger for pregnancy nausea and vomiting."),
    ("25179792", "nutrition", "all", "Dose-response meta-analysis of caffeine intake and adverse birth outcomes."),
    ("31193832", "lifestyle", "3", "Individual-participant meta-analysis of going-to-sleep position and late stillbirth risk."),
    ("31296936", "nutrition", "all", "Anaemia and iron deficiency in pregnancy and perinatal outcomes in Southern India."),
    ("37513543", "nutrition", "all", "Asian expert consensus on preventing and managing iron deficiency in women."),
    ("38889571", "nutrition", "all", "Systematic review of RCTs on the Mediterranean diet and gestational diabetes."),
    ("41089998", "mental", "all", "Narrative review of perinatal depression in India: prevalence and risk factors."),
]

# Pages whose <title> is useless on its own ("Detail", "Moaayush", ...).
TITLE_OVERRIDES = {
    "https://www.who.int/news-room/fact-sheets/detail/breastfeeding": "Breastfeeding (WHO fact sheet)",
    "https://www.who.int/news-room/fact-sheets/detail/anaemia": "Anaemia (WHO fact sheet)",
    "https://www.who.int/news-room/fact-sheets/detail/physical-activity": "Physical activity (WHO fact sheet)",
    "https://www.who.int/news-room/fact-sheets/detail/maternal-mortality": "Maternal mortality (WHO fact sheet)",
    "https://ayush.gov.in/": "Ministry of Ayush portal",
    "https://www.nin.res.in/downloads/DietaryGuidelinesforNINwebsite.pdf": "ICMR-NIN Dietary Guidelines for Indians",
    "https://poshanabhiyaan.gov.in/": "Poshan Abhiyaan - national nutrition mission",
    "https://pmmvy.wcd.gov.in/": "Pradhan Mantri Matru Vandana Yojana",
    "https://www.nhm.gov.in/index1.php?lang=1&level=2&sublinkid=822&lid=218": "Maternal health - National Health Mission",
}

TOPIC_LABELS = {
    "nutrition": "Nutrition",
    "lifestyle": "Lifestyle & exercise",
    "symptoms": "Common symptoms",
    "safety": "Warning signs & safety",
    "antenatal": "Antenatal care",
    "schemes": "Government schemes",
    "mental": "Mental wellbeing",
    "labour": "Labour & birth",
    "postnatal": "Postpartum & breastfeeding",
    "ayurveda": "Ayurveda & traditional",
    "development": "Baby's development",
}


def _json(url: str):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read())


def _video(row):
    vid, topic, stages, lang, about = row
    watch = f"https://www.youtube.com/watch?v={vid}"
    try:
        meta = _json("https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(watch, safe=""))
    except Exception as exc:  # noqa: BLE001 - report and drop
        return None, f"video {vid}: {exc}"
    return {
        "id": f"yt-{vid}",
        "type": "video",
        "topic": topic,
        "stages": stages,
        "language": lang,
        "title": meta["title"],
        "publisher": meta["author_name"],
        "url": watch,
        "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        "about": about,
    }, None


def _article(row):
    topic, stages, about, url = row
    try:
        resp = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20)
        final = resp.geturl()
        html = resp.read(400000).decode("utf8", "ignore")
    except Exception as exc:  # noqa: BLE001
        return None, f"article {url}: {exc}"
    if "/404" in final or "Page Not Found" in html[:20000]:
        return None, f"article {url}: resolves to a 404 page"
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    title = re.sub(r"\s+", " ", m.group(1)).strip() if m else about
    title = re.sub(r"^.*?<title>", "", title)
    for ent, ch in (("&#x27;", "'"), ("&amp;", "&"), ("&quot;", '"')):
        title = title.replace(ent, ch)
    title = TITLE_OVERRIDES.get(url, title)
    title = re.sub(r"\s+[-|]\s+(NHS|ACOG)$", "", title)
    host = urllib.parse.urlparse(final).netloc.removeprefix("www.")
    publisher = {
        "nhs.uk": "NHS", "who.int": "World Health Organization", "acog.org": "ACOG",
        "poshanabhiyaan.gov.in": "Government of India", "nin.res.in": "ICMR-National Institute of Nutrition",
        "pmmvy.wcd.gov.in": "Government of India", "nhm.gov.in": "National Health Mission, India",
        "ayush.gov.in": "Ministry of Ayush, India",
    }.get(host, host)
    kind = "guideline" if host in {"who.int", "pmmvy.wcd.gov.in", "nhm.gov.in", "poshanabhiyaan.gov.in", "nin.res.in"} else "article"
    return {
        "id": "web-" + re.sub(r"[^a-z0-9]+", "-", (host + urllib.parse.urlparse(final).path).lower()).strip("-")[:70],
        "type": kind, "topic": topic, "stages": stages, "language": "en",
        "title": title, "publisher": publisher, "url": final, "about": about,
    }, None


def _papers(rows):
    ids = ",".join(r[0] for r in rows)
    try:
        res = _json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&retmode=json&id={ids}")["result"]
    except Exception as exc:  # noqa: BLE001
        return [], [f"pubmed: {exc}"]
    out, errs = [], []
    for pmid, topic, stages, about in rows:
        rec = res.get(pmid)
        if not rec:
            errs.append(f"pubmed {pmid}: not found")
            continue
        out.append({
            "id": f"pm-{pmid}", "type": "research", "topic": topic, "stages": stages, "language": "en",
            "title": rec["title"].rstrip("."), "publisher": f"{rec['source']} ({rec['pubdate'][:4]})",
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "about": about,
        })
    return out, errs


def main() -> int:
    entries, errors = [], []
    with cf.ThreadPoolExecutor(8) as ex:
        for item, err in list(ex.map(_video, VIDEOS)) + list(ex.map(_article, ARTICLES)):
            (entries.append(item) if item else errors.append(err))
    papers, perrs = _papers(RESEARCH)
    entries += papers
    errors += perrs
    seen, unique = set(), []
    for e in entries:
        if e["id"] not in seen:
            seen.add(e["id"])
            unique.append(e)
    doc = {
        "verified_on": dt.date.today().isoformat(),
        "topics": TOPIC_LABELS,
        "resources": unique,
    }
    OUT.write_text(
        "# Generated by build_library.py -- re-run it to re-verify; do not hand-edit titles.\n"
        + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    print(f"wrote {len(unique)} resources to {OUT}")
    for e in errors:
        print("DROPPED:", e, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
