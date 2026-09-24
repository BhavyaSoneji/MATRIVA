from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class MessageRequest(APIModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=64)
    session_context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.replace("\x00", "").strip()
        if not value:
            raise ValueError("message must not be blank")
        if len(value) > 4000:
            raise ValueError("message is too long")
        return value

    @field_validator("session_context")
    @classmethod
    def validate_context(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, default=str)) > 8000:
            raise ValueError("session_context is too large")
        return value


class RegisterRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if value.strip() != value:
            raise ValueError("password must not start or end with whitespace")
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("password must contain a letter and a number")
        return value


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(APIModel):
    id: str
    email: EmailStr
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime


class TokenResponse(APIModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class ProfileUpdateRequest(APIModel):
    consent: bool
    consent_version: str = Field(default="2026-01", min_length=3, max_length=40)
    full_name: str | None = Field(default=None, max_length=120)
    known_conditions: list[str] = Field(default_factory=list, max_length=50)
    doctor_restrictions: list[str] = Field(default_factory=list, max_length=50)
    dietary_restrictions: list[str] = Field(default_factory=list, max_length=50)
    activity_restrictions: list[str] = Field(default_factory=list, max_length=50)
    allergies: list[str] = Field(default_factory=list, max_length=50)
    health_notes: str | None = Field(default=None, max_length=2000)
    activity_level: str | None = Field(default=None, max_length=40)
    occupation: str | None = Field(default=None, max_length=120)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    stress_level: str | None = Field(default=None, max_length=40)
    lifestyle_preferences: list[str] = Field(default_factory=list, max_length=50)
    diet_type: str | None = Field(default=None, max_length=40)
    region: str | None = Field(default=None, max_length=80)
    cuisine: str | None = Field(default=None, max_length=80)
    food_preferences: list[str] = Field(default_factory=list, max_length=50)
    language: str | None = Field(default=None, max_length=40)
    traditional_practice_preference: str | None = Field(default=None, max_length=40)
    cultural_notes: str | None = Field(default=None, max_length=2000)

    @field_validator(
        "known_conditions",
        "doctor_restrictions",
        "dietary_restrictions",
        "activity_restrictions",
        "allergies",
        "lifestyle_preferences",
        "food_preferences",
    )
    @classmethod
    def validate_string_lists(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if any(len(item) > 160 for item in cleaned):
            raise ValueError("list entries must be 160 characters or fewer")
        return list(dict.fromkeys(cleaned))


class ProfileResponse(APIModel):
    user_id: str
    consent: bool
    consent_version: str | None
    full_name: str | None
    health: dict[str, Any] | None
    lifestyle: dict[str, Any] | None
    dietary: dict[str, Any] | None
    cultural: dict[str, Any] | None


class ConsentRequest(APIModel):
    granted: bool
    version: str = Field(default="2026-01", min_length=3, max_length=40)


class PregnancyUpdateRequest(APIModel):
    current_week: int = Field(ge=1, le=42)
    due_date: date | None = None
    first_pregnancy: bool = True


class PregnancyResponse(APIModel):
    current_week: int
    due_date: date | None
    first_pregnancy: bool
    stage: str
    trimester: int


class SourceResponse(APIModel):
    id: str
    name: str
    title: str
    source_type: str
    authority: str | None
    jurisdiction: str | None
    topic: str | None
    url: str | None
    version: str | None
    publication_date: date | None
    review_status: str
    evidence_level: str
    evidence_label: str | None = None
    page_or_section: str | None = None
    extra_metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeResult(APIModel):
    chunk_id: str
    document_id: str
    document_title: str
    domain: str
    subdomain: str | None
    region: str | None
    pregnancy_stage: str | None
    content: str
    score: float
    source: SourceResponse


class KnowledgeSearchResponse(APIModel):
    query: str
    results: list[KnowledgeResult]
    count: int


class Citation(BaseModel):
    source_id: str
    source_name: str
    locator: str | None = None
    evidence_level: str


class ChatResponse(APIModel):
    conversation_id: str
    message_id: str
    answer: str
    intent: str
    safety_status: str
    sources: list[SourceResponse] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    recommendations: list["RecommendationResponse"] = Field(default_factory=list)


class ChatHistoryResponse(APIModel):
    conversation_id: str
    messages: list[dict[str, Any]]


class RecommendationResponse(APIModel):
    id: str
    domain: str
    title: str
    description: str
    reason: str
    source_documents: list[str]
    evidence_level: str
    safety_status: str
    score: float
    is_saved: bool
    created_at: datetime


class RecommendationRequest(APIModel):
    intent: str | None = Field(default=None, max_length=60)
    limit: int = Field(default=5, ge=1, le=20)


class FeedbackRequest(APIModel):
    message_id: str | None = None
    recommendation_id: str | None = None
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def exactly_one_target(self) -> "FeedbackRequest":
        if bool(self.message_id) == bool(self.recommendation_id):
            raise ValueError("provide exactly one of message_id or recommendation_id")
        return self


class FeedbackResponse(APIModel):
    id: str
    message_id: str | None
    recommendation_id: str | None
    rating: int
    comment: str | None
    created_at: datetime


class GuidelineResponse(APIModel):
    id: str
    authority: str
    jurisdiction: str
    version: str | None
    effective_date: date | None
    review_due_date: date | None
    status: str
    source: SourceResponse


class AyurvedaSourceRequest(APIModel):
    source_id: str = Field(min_length=1, max_length=64)
    book: str | None = Field(default=None, max_length=240)
    chapter: str | None = Field(default=None, max_length=160)
    verse_or_page: str | None = Field(default=None, max_length=120)
    original_text: str | None = Field(default=None, max_length=10000)
    translation: str | None = Field(default=None, max_length=10000)
    interpretation: str | None = Field(default=None, max_length=10000)
    traditional_context: str | None = Field(default=None, max_length=5000)
    evidence_label: str = Field(default="traditional", max_length=80)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("provenance")
    @classmethod
    def validate_provenance_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, default=str)) > 20000:
            raise ValueError("provenance is too large")
        return value


class GuidelineRequest(APIModel):
    source_id: str = Field(min_length=1, max_length=64)
    authority: str = Field(min_length=1, max_length=240)
    jurisdiction: str = Field(min_length=1, max_length=80)
    effective_date: date | None = None
    review_due_date: date | None = None
    status: str = Field(default="pending", pattern="^(pending|active|retired)$")
    scope_notes: str | None = Field(default=None, max_length=2000)


class DocumentMetadataRequest(APIModel):
    title: str = Field(min_length=1, max_length=300)
    domain: str = Field(min_length=1, max_length=80)
    subdomain: str | None = Field(default=None, max_length=120)
    language: str = Field(default="en", min_length=2, max_length=20)
    region: str | None = Field(default=None, max_length=80)
    pregnancy_stage: str | None = Field(default=None, max_length=40)
    source_id: str | None = None
    source_name: str | None = Field(default=None, max_length=240)
    source_type: str = Field(default="internal", max_length=40)
    authority: str | None = Field(default=None, max_length=240)
    jurisdiction: str | None = Field(default=None, max_length=80)
    evidence_level: str = Field(default="uncertain", max_length=40)
    topic: str | None = Field(default=None, max_length=120)
    url: str | None = Field(default=None, max_length=2000)
    version: str | None = Field(default=None, max_length=80)

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, value: str) -> str:
        allowed = {"government", "professional_society", "international", "academic", "traditional", "internal"}
        if value not in allowed:
            raise ValueError("unsupported source type")
        return value

    @field_validator("evidence_level")
    @classmethod
    def validate_evidence_level(cls, value: str) -> str:
        allowed = {"traditional", "preliminary", "limited_evidence", "mixed_evidence", "supported", "uncertain", "not_established"}
        if value not in allowed:
            raise ValueError("unsupported evidence level")
        return value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be an http(s) URL")
        return value


class DocumentResponse(APIModel):
    id: str
    source_id: str
    title: str
    domain: str
    subdomain: str | None
    language: str
    region: str | None
    pregnancy_stage: str | None
    review_status: str
    index_status: str
    content_hash: str
    file_name: str | None
    mime_type: str | None
    active: bool
    created_at: datetime
    updated_at: datetime
    source: SourceResponse


class FoodItemRequest(APIModel):
    name: str = Field(min_length=1, max_length=180)
    local_names: list[str] = Field(default_factory=list, max_length=30)
    region: str | None = Field(default=None, max_length=80)
    cuisine: str | None = Field(default=None, max_length=80)
    ingredients: list[str] = Field(default_factory=list, max_length=100)
    dietary_types: list[str] = Field(default_factory=list, max_length=20)
    season: str | None = Field(default=None, max_length=40)
    nutrition_metadata: dict[str, Any] = Field(default_factory=dict)
    cultural_relevance: str | None = Field(default=None, max_length=2000)
    pregnancy_context: str | None = Field(default=None, max_length=2000)
    evidence_status: str = Field(default="uncertain", pattern="^(traditional|preliminary|limited_evidence|mixed_evidence|supported|uncertain|not_established)$")
    safety_status: str = Field(default="safe_general", pattern="^(safe_general|low_concern|medical_review|high_risk|urgent_escalation|insufficient_information)$")
    source_ids: list[str] = Field(default_factory=list, max_length=30)
    active: bool = True

    @field_validator("nutrition_metadata")
    @classmethod
    def validate_nutrition_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(value, default=str)) > 20000:
            raise ValueError("nutrition_metadata is too large")
        return value


class ExerciseGuidanceRequest(APIModel):
    category: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(min_length=1, max_length=5000)
    suitable_stages: list[str] = Field(default_factory=list, max_length=10)
    restrictions: list[str] = Field(default_factory=list, max_length=50)
    evidence_status: str = Field(default="uncertain", pattern="^(traditional|preliminary|limited_evidence|mixed_evidence|supported|uncertain|not_established)$")
    safety_status: str = Field(default="safe_general", pattern="^(safe_general|low_concern|medical_review|high_risk|urgent_escalation|insufficient_information)$")
    source_ids: list[str] = Field(default_factory=list, max_length=30)
    active: bool = True


class SafetyRuleRequest(APIModel):
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=60)
    pattern: str = Field(min_length=1, max_length=300)
    response: str = Field(min_length=1, max_length=1000)
    risk_level: str = Field(default="medical_review", pattern="^(safe_general|low_concern|medical_review|high_risk|urgent_escalation)$")
    active: bool = True
    version: str = Field(default="1", max_length=40)
    reviewed_by: str | None = Field(default=None, max_length=160)


class SafetyRuleResponse(APIModel):
    id: str
    name: str
    category: str
    pattern: str
    response: str
    risk_level: str
    active: bool
    version: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SafetyEventResponse(APIModel):
    id: str
    user_id: str | None
    risk_level: str
    matched_rule_ids: list[str]
    action: str
    created_at: datetime


class EvaluationRequest(APIModel):
    suite: str = Field(default="all", pattern="^(all|retrieval|generation|safety)$")


class EvaluationResponse(APIModel):
    id: str
    suite: str
    status: str
    metrics: dict[str, Any]
    report_path: str | None
    error: str | None
    started_at: datetime
    completed_at: datetime | None


class NextVisitResponse(APIModel):
    next_visit_week: int
    current_week: int
    message: str
    source_id: str
    evidence_level: str


class DeleteResponse(APIModel):
    message: str


ChatResponse.model_rebuild()
