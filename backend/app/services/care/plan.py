"""The weekly plan: where you are, what is due, which visits are coming, what to take."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services.care.dating import Dating
from app.services.care.rules import rules

# General pregnancy-education content, sourced; one short list per trimester.
_TRIMESTER_TASKS: dict[int, list[dict[str, str]]] = {
    1: [
        {"id": "foods_avoid", "title": "Know the foods to avoid", "detail": "Alcohol, unpasteurised dairy, raw or undercooked meat and liver are the main ones.",
         "ask": "Which foods should I avoid in pregnancy?", "source": "NHS - Foods to avoid in pregnancy"},
        {"id": "sickness", "title": "Morning sickness help", "detail": "Small, frequent plain meals and sips of fluid often help; call a doctor if you cannot keep fluids down for 24 hours.",
         "ask": "What helps with morning sickness?", "source": "NHS - Morning sickness"},
        {"id": "book_visit", "title": "Book your first antenatal visit", "detail": "Early care helps find risks sooner; the first visit is usually by week 12.",
         "ask": "When are my antenatal visits?", "source": "FOGSI / WHO antenatal care model"},
    ],
    2: [
        {"id": "ifa_diet", "title": "Eat for iron, with vitamin C", "detail": "Greens, legumes and jaggery with amla, guava or citrus; keep tea away from meals.",
         "ask": "How can I improve iron absorption from vegetarian food?", "source": "ICMR-NIN Dietary Guidelines"},
        {"id": "pmsma", "title": "Use the free check-up on the 9th", "detail": "PMSMA gives a free doctor check-up at government facilities on the 9th of every month.",
         "ask": "Is there a free monthly check-up scheme in India?", "source": "MoHFW - PMSMA"},
        {"id": "move", "title": "Stay active", "detail": "Walking, swimming or prenatal yoga; if you can hold a conversation you are at a good pace.",
         "ask": "Which exercises are safe in pregnancy?", "source": "NHS - Exercise in pregnancy"},
    ],
    3: [
        {"id": "kicks", "title": "Know your baby's usual movements", "detail": "There is no set number; tell your midwife or doctor straight away if movements slow down or stop.",
         "ask": "What should I do if my baby moves less?", "source": "NHS - Your baby's movements"},
        {"id": "labour", "title": "Learn the signs of labour", "detail": "Regular contractions every 5 minutes or closer, the waters breaking, or bleeding mean call your doctor or maternity unit.",
         "ask": "How will I know labour has started?", "source": "NHS - Signs that labour has begun"},
        {"id": "breastfeeding", "title": "Prepare for breastfeeding", "detail": "WHO advises starting within the first hour and exclusive breastfeeding for six months.",
         "ask": "How long should I breastfeed exclusively?", "source": "WHO - Breastfeeding"},
    ],
}

_MILESTONES: dict[int, list[dict[str, str]]] = {
    1: [{"title": "Major organs begin forming", "detail": "The heart, brain and spinal cord start to develop."},
        {"title": "Heartbeat may be detectable", "detail": "Around week 6-8, on ultrasound."}],
    2: [{"title": "Movements may be felt", "detail": "Many mothers notice fluttering movements."},
        {"title": "Anatomy scan window", "detail": "A detailed ultrasound is typically around week 18-20."}],
    3: [{"title": "Rapid weight gain", "detail": "Baby gains most of their birth weight now."},
        {"title": "Head-down positioning", "detail": "Baby typically settles head-down before delivery."}],
}


def _date_of_week(lmp: date, week: int) -> date:
    return lmp + timedelta(days=(week - 1) * 7)


def visits(d: Dating, today: date) -> list[dict[str, Any]]:
    out = []
    for w in rules()["visit_schedule"]["weeks"]:
        when = _date_of_week(d.lmp, w)
        if w < d.week:
            status = "past"
        elif w == d.week:
            status = "due_now"
        else:
            status = "upcoming"
        out.append({"week": w, "date": when.isoformat(), "days_away": (when - today).days, "status": status})
    return out


def next_pmsma(today: date, week: int) -> dict[str, Any] | None:
    cfg = rules()["pmsma"]
    if week < cfg["from_week"] - 1:
        return None
    day = cfg["day_of_month"]
    candidate = today.replace(day=day) if today.day <= day else (today.replace(day=1) + timedelta(days=32)).replace(day=day)
    return {"date": candidate.isoformat(), "days_away": (candidate - today).days, "note": cfg["note"], "source": cfg["source"], "url": cfg["url"]}


def supplements(d: Dating) -> list[dict[str, Any]]:
    out = []
    for s in rules()["supplements"]:
        start, end = s.get("from_week", 1), s.get("until_week", 99)
        if s.get("days"):
            end = start + s["days"] // 7 + 1
        out.append({
            "id": s["id"], "label": s["label"], "active": start <= d.week <= end,
            "from_week": s.get("from_week"), "until_week": s.get("until_week"),
            "instruction": s["instruction"], "source": s["source"], "url": s["url"],
        })
    return out


def build_plan(d: Dating, today: date) -> dict[str, Any]:
    vs = visits(d, today)
    upcoming = [v for v in vs if v["status"] in {"due_now", "upcoming"}]
    nxt = upcoming[0] if upcoming else None
    active_supplements = [s for s in supplements(d) if s["active"]]
    this_week = []
    for s in active_supplements:
        this_week.append({"id": f"supp_{s['id']}", "title": s["label"], "detail": s["instruction"], "source": s["source"], "kind": "supplement"})
    if nxt and nxt["days_away"] <= 14:
        this_week.append({"id": "visit", "title": "Antenatal visit coming up", "kind": "visit", "source": "FOGSI / WHO antenatal care model",
                          "detail": f"Visit around week {nxt['week']} ({nxt['date']}). Bring your reports and your questions."})
    this_week.extend({**t, "kind": "learn"} for t in _TRIMESTER_TASKS[d.trimester])
    return {
        "week": d.week, "day": d.day, "trimester": d.trimester, "stage": d.stage,
        "lmp": d.lmp.isoformat(), "edd": d.edd.isoformat(), "days_to_edd": d.days_to_edd,
        "progress": round(d.progress, 3), "source_of_dates": d.source,
        "headline": f"Week {d.week}, day {d.day} - trimester {d.trimester}",
        "next_visit": nxt, "visits": vs, "pmsma": next_pmsma(today, d.week),
        "supplements": supplements(d), "this_week": this_week, "milestones": _MILESTONES[d.trimester],
        "review": rules()["visit_schedule"]["review"],
    }
