"""What the guard rails know about the person asking: week, conditions, medicines, allergies, risk factors.

Health details are only read when the user has given consent (the same gate that protects storing them).
Free-text conditions are mapped to canonical codes through the alias lists in ``conditions.yaml``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import HealthProfile, PregnancyProfile, User
from app.safety.guardrails.registry import load_registry
from app.safety.guardrails.text import normalize
from app.services.profile import has_consent


@dataclass
class GuardContext:
    week: int | None = None
    conditions: set[str] = field(default_factory=set)
    risk_factors: set[str] = field(default_factory=set)
    medications: list[str] = field(default_factory=list)  # normalised names the user listed
    allergies: list[str] = field(default_factory=list)  # normalised
    age: int | None = None
    language: str | None = None

    @property
    def known(self) -> bool:
        return bool(self.week or self.conditions or self.medications or self.allergies or self.risk_factors or self.age)


def canonical_conditions(raw_items: list[str]) -> set[str]:
    registry = load_registry()
    found: set[str] = set()
    for item in raw_items:
        text = f" {normalize(item)} "
        for code, spec in registry.conditions.items():
            if any(f" {normalize(alias)} " in text for alias in spec.get("aliases", [code])):
                found.add(code)
    return found


def build_guard_context(db: Session, user: User | None, language: str | None = None) -> GuardContext:
    ctx = GuardContext(language=language)
    if user is None:
        return ctx
    pregnancy = db.execute(select(PregnancyProfile).where(PregnancyProfile.user_id == user.id)).scalar_one_or_none()
    if pregnancy:
        ctx.week = pregnancy.current_week
    if not has_consent(db, user.id):
        return ctx
    health = db.execute(select(HealthProfile).where(HealthProfile.user_id == user.id)).scalar_one_or_none()
    if health is None:
        return ctx
    ctx.conditions = canonical_conditions([*(health.known_conditions or []), *(health.doctor_restrictions or [])])
    ctx.risk_factors = {code for code in (health.risk_factors or []) if code in load_registry().risk_factors}
    ctx.medications = [normalize(m) for m in (health.current_medications or []) if normalize(m)]
    ctx.allergies = [normalize(a) for a in (health.allergies or []) if normalize(a)]
    ctx.age = health.age_years
    if "rh_negative" not in ctx.risk_factors and (health.blood_group or "").strip().lower().endswith(("-", "neg", "negative")):
        ctx.risk_factors.add("rh_negative")
    if ctx.age is not None:
        if ctx.age < 18:
            ctx.risk_factors.add("age_under_18")
        elif ctx.age >= 35:
            ctx.risk_factors.add("age_35_plus")
    return ctx
