from __future__ import annotations

from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CareModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class DatingRequest(CareModel):
    """Exactly one of the three ways to say how far along you are."""

    lmp_date: Date | None = None
    edd_date: Date | None = None
    current_week: int | None = Field(default=None, ge=1, le=42)
    pre_pregnancy_weight_kg: float | None = Field(default=None, ge=25, le=200)
    first_pregnancy: bool | None = None


class CheckinRequest(CareModel):
    date: Date | None = None
    mood: int | None = Field(default=None, ge=1, le=5)
    symptoms: list[str] = Field(default_factory=list, max_length=20)
    baby_movement: str | None = Field(default=None, pattern="^(normal|reduced|not_yet)$")
    ifa_taken: bool | None = None
    note: str | None = Field(default=None, max_length=500)
    red_flags: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("symptoms")
    @classmethod
    def _short(cls, v: list[str]) -> list[str]:
        return [s[:40] for s in v]


class ReadingRequest(CareModel):
    kind: str = Field(pattern="^(hb|bp|weight|glucose)$")
    date: Date | None = None
    value: float | None = None
    systolic: int | None = None
    diastolic: int | None = None
    context: str | None = Field(default=None, max_length=30)
    note: str | None = Field(default=None, max_length=300)
    source: str = Field(default="manual", pattern="^(manual|report|ocr|chat)$")


class ReportTextRequest(CareModel):
    text: str = Field(min_length=3, max_length=20000)


class MealRequest(CareModel):
    text: str = Field(min_length=2, max_length=500)
    date: Date | None = None
    meal_type: str | None = Field(default=None, pattern="^(breakfast|lunch|dinner|snack)$")


class ScreeningRequest(CareModel):
    answers: dict[str, bool] = Field(max_length=40)


class EmergencyContactRequest(CareModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=5, max_length=32, pattern=r"^[0-9+\-\s()]{5,32}$")
    relation: str | None = Field(default=None, max_length=60)
