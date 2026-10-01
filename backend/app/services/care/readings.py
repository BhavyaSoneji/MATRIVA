"""Health readings (haemoglobin, blood pressure, weight, blood sugar): storage, flags, trends, report parsing, OCR.

Flags are shown as "ask your doctor", never as a diagnosis, and every flag carries the source of its threshold
(app/data/care_rules.yaml, pending clinical review).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HealthReading, User
from app.services.care.dating import Dating
from app.services.care.rules import rules

KINDS = ("hb", "bp", "weight", "glucose")
MAX_IMAGE_BYTES = 8_000_000
IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


class ReadingError(ValueError):
    pass


class OcrUnavailable(RuntimeError):
    pass


def validate(kind: str, value: float | None, systolic: int | None, diastolic: int | None) -> None:
    if kind not in KINDS:
        raise ReadingError(f"kind must be one of {', '.join(KINDS)}")
    cfg = rules()["readings"][kind]
    if kind == "bp":
        if systolic is None or diastolic is None:
            raise ReadingError("Blood pressure needs both numbers, for example 120 and 80.")
        if not (60 <= systolic <= 260 and 30 <= diastolic <= 180) or diastolic >= systolic:
            raise ReadingError("Those blood pressure numbers do not look right. Please check them.")
        return
    if value is None or not cfg["min"] <= value <= cfg["max"]:
        raise ReadingError(f"{cfg['label']} should be between {cfg['min']} and {cfg['max']} {cfg['unit']}.")


def add(db: Session, user: User, kind: str, day: date, *, value: float | None = None, systolic: int | None = None,
        diastolic: int | None = None, context: str | None = None, note: str | None = None, source: str = "manual",
        today: date | None = None) -> HealthReading:
    validate(kind, value, systolic, diastolic)
    if day > (today or date.today()) + timedelta(days=1):
        raise ReadingError("A reading cannot be dated in the future.")
    row = HealthReading(user_id=user.id, kind=kind, reading_date=day, value=value, systolic=systolic, diastolic=diastolic,
                        context=context, note=note, source=source)
    db.add(row)
    db.flush()
    return row


def flags(row: HealthReading) -> list[dict[str, str]]:
    """Messages about one reading. level: urgent (act today), discuss (tell your doctor), info."""
    out: list[dict[str, str]] = []
    cfg = rules()["readings"].get(row.kind, {})
    if row.kind == "hb" and row.value is not None and row.value < cfg["low"]:
        out.append({"level": "discuss", "message": cfg["low_message"], "source": cfg["source"], "url": cfg["url"]})
    if row.kind == "bp" and row.systolic is not None:
        if row.systolic >= cfg["systolic_severe"] or row.diastolic >= cfg["diastolic_severe"]:
            out.append({"level": "urgent", "message": cfg["severe_message"], "source": cfg["source"], "url": cfg["url"]})
        elif row.systolic >= cfg["systolic_high"] or row.diastolic >= cfg["diastolic_high"]:
            out.append({"level": "urgent", "message": cfg["high_message"], "source": cfg["source"], "url": cfg["url"]})
    if row.kind == "glucose":
        out.append({"level": "info", "message": cfg["note"], "source": cfg["source"], "url": cfg["url"]})
    return out


def payload(row: HealthReading) -> dict[str, Any]:
    return {
        "id": row.id, "kind": row.kind, "date": row.reading_date.isoformat(), "value": row.value, "systolic": row.systolic,
        "diastolic": row.diastolic, "context": row.context, "note": row.note, "source": row.source,
        "unit": rules()["readings"][row.kind]["unit"], "flags": flags(row),
    }


def history(db: Session, user: User, kind: str | None = None, days: int = 365, today: date | None = None) -> list[HealthReading]:
    since = (today or date.today()) - timedelta(days=days)
    stmt = select(HealthReading).where(HealthReading.user_id == user.id, HealthReading.reading_date >= since)
    if kind:
        stmt = stmt.where(HealthReading.kind == kind)
    return list(db.execute(stmt.order_by(HealthReading.reading_date, HealthReading.created_at)).scalars().all())


def weight_gain(rows: list[HealthReading], dating: Dating | None) -> dict[str, Any] | None:
    """Gain so far against the ICMR-NIN whole-pregnancy range, from the pre-pregnancy weight if known."""
    weights = [r for r in rows if r.kind == "weight" and r.value]
    if not weights:
        return None
    base = dating.pre_pregnancy_weight_kg if dating and dating.pre_pregnancy_weight_kg else None
    base_label = "pre-pregnancy weight" if base else "first recorded weight"
    base = base or weights[0].value
    latest = weights[-1].value
    cfg = rules()["readings"]["weight"]
    lo, hi = cfg["total_gain_range"]
    return {"baseline_kg": base, "baseline": base_label, "latest_kg": latest, "gain_kg": round(latest - base, 1),
            "healthy_total_gain_kg": [lo, hi], "note": cfg["gain_message"], "source": cfg["source"], "url": cfg["url"]}


# ------------------------------------------------------------------------------------------------ report parsing
_DATE = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b|\b(\d{4})-(\d{2})-(\d{2})\b")
_HB = re.compile(r"\b(?:hb|hgb|haemoglobin|hemoglobin)\b(?:\s*(?:is|was|of|came|at|about|around)\b)?\s*[:=\-]?\s*(\d{1,3}(?:\.\d{1,2})?)\s*(g\s*/?\s*d?l|gm\s*%?|g%|g/l)?", re.I)
_BP = re.compile(r"(?:\b(?:bp|blood pressure)\b(?:\s*(?:is|was|of|came|at|about|around)\b)?\s*[:=\-]?\s*)(\d{2,3})\s*[/\\]\s*(\d{2,3})|\b(\d{2,3})\s*[/\\]\s*(\d{2,3})\s*mm\s*hg", re.I)
_WEIGHT = re.compile(r"\b(?:weight|wt)\b(?:\s*(?:is|was|of|came|at|about|around)\b)?\s*[:=\-]?\s*(\d{2,3}(?:\.\d)?)\s*kgs?\b", re.I)
_GLUCOSE = re.compile(r"\b(fasting|fbs|ppbs|pp|post[\s-]?prandial|random|rbs)?\s*(?:blood\s*)?(?:glucose|sugar|fbs|ppbs|rbs)\b(?:\s*(?:is|was|of|came|at|about|around)\b)?\s*[:=\-]?\s*(\d{2,3}(?:\.\d)?)\s*(?:mg\s*/?\s*dl)?", re.I)


def _find_date(text: str, fallback: date) -> date:
    m = _DATE.search(text)
    if not m:
        return fallback
    try:
        if m.group(1):
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return date(2000 + y if y < 100 else y, mo, d)
        return date(int(m.group(4)), int(m.group(5)), int(m.group(6)))
    except ValueError:
        return fallback


def parse_report_text(text: str, today: date | None = None) -> list[dict[str, Any]]:
    """Candidate readings found in the text of a lab report or prescription. The user confirms them before they are saved:
    OCR and regexes make mistakes, and a wrong haemoglobin could mislead."""
    today = today or date.today()
    when = _find_date(text, today).isoformat()
    out: list[dict[str, Any]] = []
    for m in _HB.finditer(text):
        v = float(m.group(1))
        if (m.group(2) or "").lower().replace(" ", "") == "g/l" or v > 30:
            v = round(v / 10, 1)
        out.append({"kind": "hb", "value": v, "date": when, "matched": m.group(0).strip()})
    for m in _BP.finditer(text):
        sys_, dia = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        out.append({"kind": "bp", "systolic": int(sys_), "diastolic": int(dia), "date": when, "matched": m.group(0).strip()})
    for m in _WEIGHT.finditer(text):
        out.append({"kind": "weight", "value": float(m.group(1)), "date": when, "matched": m.group(0).strip()})
    for m in _GLUCOSE.finditer(text):
        ctx = (m.group(1) or "").lower()
        out.append({"kind": "glucose", "value": float(m.group(2)), "date": when, "matched": m.group(0).strip(),
                    "context": "fasting" if ctx in {"fasting", "fbs"} else "after_meal" if ctx.startswith(("pp", "post")) else "random" if ctx else None})
    valid = []
    for c in out:
        try:
            validate(c["kind"], c.get("value"), c.get("systolic"), c.get("diastolic"))
            valid.append(c)
        except ReadingError:
            continue
    return valid


def ocr_image(data: bytes, content_type: str) -> str:
    """Read text from a photo of a report with the local `tesseract` program. Nothing leaves the machine."""
    if content_type not in IMAGE_TYPES:
        raise ReadingError("Upload a PNG, JPEG or WebP photo.")
    if len(data) > MAX_IMAGE_BYTES:
        raise ReadingError("That photo is too large (8 MB limit).")
    binary = shutil.which("tesseract")
    if binary is None:
        raise OcrUnavailable("Photo reading is not available on this server. Paste the report text instead.")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "report"
        path.write_bytes(data)
        try:
            proc = subprocess.run([binary, str(path), "stdout", "-l", "eng", "--psm", "6"], capture_output=True, text=True, timeout=45, check=False)
        except subprocess.TimeoutExpired as exc:
            raise OcrUnavailable("Reading the photo took too long. Try a clearer, smaller photo.") from exc
    if proc.returncode != 0:
        raise ReadingError("Could not read that photo. Try a clearer one, or paste the text.")
    return proc.stdout
