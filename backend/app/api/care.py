"""Care endpoints: dating, plan, reminders, check-ins, readings, meals, red-flag screening, doctor summary."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.models import DietaryProfile, EmergencyContact, HealthProfile, HealthReading, MealLog
from app.schemas.api import DeleteResponse
from app.schemas.care import (
    CheckinRequest,
    DatingRequest,
    EmergencyContactRequest,
    MealRequest,
    ReadingRequest,
    ReportTextRequest,
    ScreeningRequest,
)
from app.services.audit import record_audit, record_safety_event
from app.core.security import hash_for_log
from app.services.care import dating as dating_module
from app.services.care import meals as meals_module
from app.services.care import readings as readings_module
from app.services.care import screening as screening_module
from app.services.care import summary as summary_module
from app.services.care import tracking
from app.services.care.plan import build_plan
from app.services.profile import ConsentRequired, has_consent

router = APIRouter(prefix="/care", tags=["care"])


def _need_consent(db, user) -> None:
    if not has_consent(db, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Explicit consent is required before health data can be stored")


def _dating(db, user):
    d = dating_module.resolve(db, user)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tell us how far along you are first (last period date, due date or week).")
    return d


def _contact(db, user) -> dict[str, str] | None:
    c = db.execute(select(EmergencyContact).where(EmergencyContact.user_id == user.id)).scalar_one_or_none()
    return None if c is None else {"name": c.name, "phone": c.phone, "relation": c.relation or ""}


# ----------------------------------------------------------------------------------------------- dating and plan
@router.put("/dating")
def set_dating(payload: DatingRequest, user: CurrentUser, db: DBSession) -> dict[str, object]:
    try:
        d = dating_module.save(
            db, user, lmp=payload.lmp_date, edd=payload.edd_date, week=payload.current_week,
            pre_pregnancy_weight_kg=payload.pre_pregnancy_weight_kg, first_pregnancy=payload.first_pregnancy,
        )
    except ConsentRequired as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except dating_module.DatingError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    db.commit()
    return build_plan(d, dating_module.today_utc())


@router.get("/plan")
def get_plan(user: CurrentUser, db: DBSession) -> dict[str, object]:
    dating_module.refresh_profile(db, user)
    db.commit()
    return build_plan(_dating(db, user), dating_module.today_utc())


@router.get("/reminders")
def get_reminders(user: CurrentUser, db: DBSession) -> dict[str, object]:
    today = dating_module.today_utc()
    d = dating_module.resolve(db, user, today)
    if d is None:
        return {"reminders": [], "week": None}
    return {"week": d.week, "reminders": tracking.reminders(db, user, d, today)}


# ----------------------------------------------------------------------------------------------- check-in
@router.put("/checkin")
def put_checkin(payload: CheckinRequest, user: CurrentUser, db: DBSession) -> dict[str, object]:
    _need_consent(db, user)
    today = dating_module.today_utc()
    day = payload.date or today
    if day > today:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A check-in cannot be dated in the future.")
    d = dating_module.resolve(db, user, today)
    week = d.week if d else None
    row = tracking.upsert_checkin(
        db, user, day, mood=payload.mood, symptoms=payload.symptoms, baby_movement=payload.baby_movement,
        ifa_taken=payload.ifa_taken, note=payload.note, red_flags=payload.red_flags,
    )
    out = tracking.checkin_payload(row, week)
    if out and out["triage_level"] in {"emergency", "urgent"}:
        record_safety_event(db, user_id=user.id, query_hash=hash_for_log("checkin"), risk_level=out["triage_level"],
                            matched_rule_ids=out["red_flags"], action="checkin_red_flag")
    db.commit()
    result = screening_module.assess({f: True for f in out["red_flags"]}, week, _contact(db, user)) if out["red_flags"] else None
    return {"checkin": out, "triage": result}


@router.get("/checkin")
def read_checkin(user: CurrentUser, db: DBSession, date_: date | None = Query(default=None, alias="date")) -> dict[str, object]:
    today = dating_module.today_utc()
    d = dating_module.resolve(db, user, today)
    row = tracking.get_checkin(db, user, date_ or today)
    return {"checkin": tracking.checkin_payload(row, d.week if d else None), "symptom_options": tracking.SYMPTOMS}


@router.get("/checkin/summary")
def checkin_summary(user: CurrentUser, db: DBSession, days: int = Query(default=14, ge=1, le=90)) -> dict[str, object]:
    return tracking.adherence(db, user, dating_module.today_utc(), days)


# ----------------------------------------------------------------------------------------------- readings
@router.post("/readings", status_code=status.HTTP_201_CREATED)
def add_reading(payload: ReadingRequest, user: CurrentUser, db: DBSession) -> dict[str, object]:
    _need_consent(db, user)
    try:
        row = readings_module.add(
            db, user, payload.kind, payload.date or dating_module.today_utc(), value=payload.value, systolic=payload.systolic,
            diastolic=payload.diastolic, context=payload.context, note=payload.note, source=payload.source,
        )
    except readings_module.ReadingError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    out = readings_module.payload(row)
    if any(f["level"] == "urgent" for f in out["flags"]):
        record_safety_event(db, user_id=user.id, query_hash=hash_for_log(f"reading:{row.kind}"), risk_level="urgent_escalation",
                            matched_rule_ids=[f"reading:{row.kind}"], action="reading_flag")
    db.commit()
    return out


@router.get("/readings")
def list_readings(user: CurrentUser, db: DBSession, kind: str | None = Query(default=None, pattern="^(hb|bp|weight|glucose)$"),
                  days: int = Query(default=365, ge=1, le=1200)) -> dict[str, object]:
    today = dating_module.today_utc()
    rows = readings_module.history(db, user, kind, days, today)
    d = dating_module.resolve(db, user, today)
    return {"readings": [readings_module.payload(r) for r in rows], "weight_gain": readings_module.weight_gain(rows, d) if kind in (None, "weight") else None}


@router.delete("/readings/{reading_id}", response_model=DeleteResponse)
def delete_reading(reading_id: str, user: CurrentUser, db: DBSession) -> DeleteResponse:
    row = db.get(HealthReading, reading_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reading not found")
    db.delete(row)
    db.commit()
    return DeleteResponse(message="Reading deleted")


@router.post("/readings/parse-report")
def parse_report(payload: ReportTextRequest, user: CurrentUser) -> dict[str, object]:
    """Find readings in pasted lab-report text. Nothing is saved: the user confirms each value first."""
    return {"candidates": readings_module.parse_report_text(payload.text, dating_module.today_utc())}


@router.post("/readings/ocr")
async def ocr_report(user: CurrentUser, file: UploadFile = File(...)) -> dict[str, object]:  # noqa: B008
    data = await file.read(readings_module.MAX_IMAGE_BYTES + 1)
    try:
        text = readings_module.ocr_image(data, file.content_type or "")
    except readings_module.OcrUnavailable as exc:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, str(exc)) from exc
    except readings_module.ReadingError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return {"text": text, "candidates": readings_module.parse_report_text(text, dating_module.today_utc())}


# ----------------------------------------------------------------------------------------------- meals
def _diet_and_allergies(db, user) -> tuple[str | None, list[str]]:
    diet = db.execute(select(DietaryProfile).where(DietaryProfile.user_id == user.id)).scalar_one_or_none()
    health = db.execute(select(HealthProfile).where(HealthProfile.user_id == user.id)).scalar_one_or_none()
    allergies = sorted({*(health.allergies if health else []), *(diet.allergies if diet else [])})
    return (diet.diet_type if diet else None), allergies


@router.post("/meals", status_code=status.HTTP_201_CREATED)
def add_meal(payload: MealRequest, user: CurrentUser, db: DBSession) -> dict[str, object]:
    _need_consent(db, user)
    day = payload.date or dating_module.today_utc()
    row, parsed = meals_module.log(db, user, day, payload.text, payload.meal_type)
    if row is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "I could not recognise any food there. Try names like dal, roti, rice, curd, milk, banana. Not understood: " + "; ".join(parsed["unknown"]))
    db.commit()
    return {"meal_id": row.id, "items": row.items, "totals": row.totals, "not_understood": parsed["unknown"]}


@router.get("/meals")
def day_meals(user: CurrentUser, db: DBSession, date_: date | None = Query(default=None, alias="date")) -> dict[str, object]:
    day = date_ or dating_module.today_utc()
    rows, totals = meals_module.day_totals(db, user, day)
    diet, allergies = _diet_and_allergies(db, user)
    return {
        "date": day.isoformat(),
        "meals": [{"id": r.id, "meal_type": r.meal_type, "text": r.raw_text, "items": r.items, "totals": r.totals} for r in rows],
        "totals": totals, **meals_module.gaps(totals, diet, allergies),
        "note": "Portions and Indian-food matches are approximate; values come from USDA data. The allowance is the US pregnancy RDA (pending clinical review).",
    }


@router.delete("/meals/{meal_id}", response_model=DeleteResponse)
def delete_meal(meal_id: str, user: CurrentUser, db: DBSession) -> DeleteResponse:
    row = db.get(MealLog, meal_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Meal not found")
    db.delete(row)
    db.commit()
    return DeleteResponse(message="Meal deleted")


# ----------------------------------------------------------------------------------------------- screening
@router.get("/screening/questions")
def screening_questions(user: CurrentUser, db: DBSession) -> dict[str, object]:
    d = dating_module.resolve(db, user)
    return {"week": d.week if d else None, "questions": screening_module.questions_for(d.week if d else None), "review": "pending_clinical_review"}


@router.post("/screening/assess")
def screening_assess(payload: ScreeningRequest, user: CurrentUser, db: DBSession) -> dict[str, object]:
    d = dating_module.resolve(db, user)
    week = d.week if d else None
    result = screening_module.assess(payload.answers, week, _contact(db, user))
    screening_module.record(db, user, result, week)
    if result["level"] in {"emergency", "urgent"}:
        record_safety_event(db, user_id=user.id, query_hash=hash_for_log("screening"), risk_level=f"{result['level']}_escalation" if result["level"] == "urgent" else "urgent_escalation",
                            matched_rule_ids=[f["id"] for f in result["flagged"]], action="screening")
    db.commit()
    return result


# ----------------------------------------------------------------------------------------------- summary, contact
@router.get("/summary")
def doctor_summary(user: CurrentUser, db: DBSession) -> dict[str, object]:
    record_audit(db, actor_user_id=user.id, action="care.summary_view", resource_type="user", resource_id=user.id)
    db.commit()
    return summary_module.build(db, user, dating_module.today_utc())


@router.put("/emergency-contact")
def put_contact(payload: EmergencyContactRequest, user: CurrentUser, db: DBSession) -> dict[str, str]:
    _need_consent(db, user)
    row = db.execute(select(EmergencyContact).where(EmergencyContact.user_id == user.id)).scalar_one_or_none() or EmergencyContact(user_id=user.id, name="", phone="")
    row.name, row.phone, row.relation = payload.name, payload.phone, payload.relation
    db.add(row)
    db.commit()
    return {"name": row.name, "phone": row.phone, "relation": row.relation or ""}


@router.get("/emergency-contact")
def get_contact(user: CurrentUser, db: DBSession) -> dict[str, object]:
    return {"contact": _contact(db, user), "emergency_numbers": screening_module.EMERGENCY_NUMBERS, "maps_url": screening_module.MAPS_URL}


@router.delete("/emergency-contact", response_model=DeleteResponse)
def delete_contact(user: CurrentUser, db: DBSession) -> DeleteResponse:
    row = db.execute(select(EmergencyContact).where(EmergencyContact.user_id == user.id)).scalar_one_or_none()
    if row:
        db.delete(row)
        db.commit()
    return DeleteResponse(message="Emergency contact removed")
