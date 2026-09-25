from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def new_id() -> str:
    return uuid.uuid4().hex


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(StrEnum):
    USER = "user"
    EVALUATOR = "evaluator"
    ADMIN = "admin"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class EvidenceLevel(StrEnum):
    TRADITIONAL = "traditional"
    PRELIMINARY = "preliminary"
    LIMITED_EVIDENCE = "limited_evidence"
    MIXED_EVIDENCE = "mixed_evidence"
    SUPPORTED = "supported"
    UNCERTAIN = "uncertain"
    NOT_ESTABLISHED = "not_established"


class SourceType(StrEnum):
    GOVERNMENT = "government"
    PROFESSIONAL_SOCIETY = "professional_society"
    INTERNATIONAL = "international"
    ACADEMIC = "academic"
    TRADITIONAL = "traditional"
    INTERNAL = "internal"
    # A live web search result (app.rag.web_search), never a reviewed local
    # knowledge_sources row -- always paired with EvidenceLevel.UNCERTAIN,
    # never persisted to knowledge_sources itself.
    EXTERNAL_WEB = "external_web"


class SafetyStatus(StrEnum):
    SAFE_GENERAL = "safe_general"
    LOW_CONCERN = "low_concern"
    MEDICAL_REVIEW = "medical_review"
    HIGH_RISK = "high_risk"
    URGENT_ESCALATION = "urgent_escalation"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class RiskLevel(StrEnum):
    SAFE_GENERAL = "safe_general"
    LOW_CONCERN = "low_concern"
    MEDICAL_REVIEW = "medical_review"
    HIGH_RISK = "high_risk"
    URGENT_ESCALATION = "urgent_escalation"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class IndexStatus(StrEnum):
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32), default=UserRole.USER.value, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    consent_version: Mapped[str | None] = mapped_column(String(40))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    health_profile: Mapped[HealthProfile | None] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    lifestyle_profile: Mapped[LifestyleProfile | None] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    dietary_profile: Mapped[DietaryProfile | None] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    cultural_profile: Mapped[CulturalProfile | None] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    pregnancy_profile: Mapped[PregnancyProfile | None] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    conversations: Mapped[list[Conversation]] = relationship(back_populates="user", cascade="all, delete-orphan")
    recommendations: Mapped[list[Recommendation]] = relationship(back_populates="user", cascade="all, delete-orphan")
    feedback: Mapped[list[Feedback]] = relationship(back_populates="user", cascade="all, delete-orphan")
    consent_records: Mapped[list[ConsentRecord]] = relationship(back_populates="user", cascade="all, delete-orphan")
    wellness_logs: Mapped[list[DailyWellnessLog]] = relationship(back_populates="user", cascade="all, delete-orphan")


class HealthProfile(Base):
    __tablename__ = "health_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    known_conditions: Mapped[list[str]] = mapped_column(JSON, default=list)
    doctor_restrictions: Mapped[list[str]] = mapped_column(JSON, default=list)
    dietary_restrictions: Mapped[list[str]] = mapped_column(JSON, default=list)
    activity_restrictions: Mapped[list[str]] = mapped_column(JSON, default=list)
    allergies: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="health_profile")


class LifestyleProfile(Base):
    __tablename__ = "lifestyle_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    activity_level: Mapped[str | None] = mapped_column(String(40))
    occupation: Mapped[str | None] = mapped_column(String(120))
    sleep_hours: Mapped[float | None] = mapped_column()
    stress_level: Mapped[str | None] = mapped_column(String(40))
    preferences: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="lifestyle_profile")


class DietaryProfile(Base):
    __tablename__ = "dietary_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    diet_type: Mapped[str | None] = mapped_column(String(40))
    region: Mapped[str | None] = mapped_column(String(80), index=True)
    cuisine: Mapped[str | None] = mapped_column(String(80))
    food_preferences: Mapped[list[str]] = mapped_column(JSON, default=list)
    allergies: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="dietary_profile")


class CulturalProfile(Base):
    __tablename__ = "cultural_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    language: Mapped[str | None] = mapped_column(String(40))
    region: Mapped[str | None] = mapped_column(String(80))
    traditional_practice_preference: Mapped[str | None] = mapped_column(String(40))
    cultural_notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="cultural_profile")


class PregnancyProfile(Base):
    __tablename__ = "pregnancy_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    current_week: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    first_pregnancy: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="pregnancy_profile")


class DailyWellnessLog(Base):
    __tablename__ = "daily_wellness_logs"
    __table_args__ = (UniqueConstraint("user_id", "log_date", name="uq_wellness_user_date"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    water_intake_ml: Mapped[float | None] = mapped_column()
    sleep_hours: Mapped[float | None] = mapped_column()
    activity_minutes: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="wellness_logs")


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    consent_type: Mapped[str] = mapped_column(String(80), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="consent_records")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160), default="MATRIVA conversation")
    session_context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user: Mapped[User | None] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conversation_created", "conversation_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(60))
    safety_status: Mapped[str | None] = mapped_column(String(40))
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    feedback: Mapped[list[Feedback]] = relationship(back_populates="message")


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), default=SourceType.INTERNAL.value, nullable=False)
    authority: Mapped[str | None] = mapped_column(String(240))
    jurisdiction: Mapped[str | None] = mapped_column(String(80), index=True)
    topic: Mapped[str | None] = mapped_column(String(120), index=True)
    url: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str | None] = mapped_column(String(80))
    publication_date: Mapped[date | None] = mapped_column(Date)
    review_status: Mapped[str] = mapped_column(String(30), default=ReviewStatus.PENDING.value, nullable=False, index=True)
    evidence_level: Mapped[str] = mapped_column(String(40), default=EvidenceLevel.UNCERTAIN.value, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    documents: Mapped[list[KnowledgeDocument]] = relationship(back_populates="source", cascade="all, delete-orphan")
    evidence_metadata: Mapped[EvidenceMetadata | None] = relationship(back_populates="source", uselist=False, cascade="all, delete-orphan")
    ayurvedic_source: Mapped[AyurvedicSource | None] = relationship(back_populates="source", uselist=False, cascade="all, delete-orphan")
    guideline: Mapped[Guideline | None] = relationship(back_populates="source", uselist=False, cascade="all, delete-orphan")


class EvidenceMetadata(Base):
    __tablename__ = "evidence_metadata"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("knowledge_sources.id", ondelete="CASCADE"), unique=True, nullable=False)
    evidence_level: Mapped[str] = mapped_column(String(40), default=EvidenceLevel.UNCERTAIN.value, nullable=False)
    evidence_label: Mapped[str | None] = mapped_column(String(80))
    review_status: Mapped[str] = mapped_column(String(30), default=ReviewStatus.PENDING.value, nullable=False)
    reviewer: Mapped[str | None] = mapped_column(String(160))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    source: Mapped[KnowledgeSource] = relationship(back_populates="evidence_metadata")


class Guideline(Base):
    __tablename__ = "guideline_registry"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("knowledge_sources.id", ondelete="CASCADE"), unique=True, nullable=False)
    authority: Mapped[str] = mapped_column(String(240), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(80), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date)
    review_due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    scope_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    source: Mapped[KnowledgeSource] = relationship(back_populates="guideline")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("knowledge_sources.id", ondelete="RESTRICT"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    domain: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    subdomain: Mapped[str | None] = mapped_column(String(120), index=True)
    language: Mapped[str] = mapped_column(String(20), default="en", nullable=False)
    region: Mapped[str | None] = mapped_column(String(80), index=True)
    pregnancy_stage: Mapped[str | None] = mapped_column(String(40), index=True)
    review_status: Mapped[str] = mapped_column(String(30), default=ReviewStatus.PENDING.value, nullable=False, index=True)
    index_status: Mapped[str] = mapped_column(String(30), default=IndexStatus.PENDING.value, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_name: Mapped[str | None] = mapped_column(String(220))
    mime_type: Mapped[str | None] = mapped_column(String(160))
    storage_path: Mapped[str | None] = mapped_column(Text)
    raw_content: Mapped[bytes | None] = mapped_column(LargeBinary)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    source: Mapped[KnowledgeSource] = relationship(back_populates="documents")
    chunks: Mapped[list[KnowledgeChunk]] = relationship(back_populates="document", cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(JSON)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")
    source: Mapped[KnowledgeSource] = relationship()


class AyurvedicSource(Base):
    __tablename__ = "ayurvedic_sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("knowledge_sources.id", ondelete="CASCADE"), unique=True, nullable=False)
    book: Mapped[str | None] = mapped_column(String(240))
    chapter: Mapped[str | None] = mapped_column(String(160))
    verse_or_page: Mapped[str | None] = mapped_column(String(120))
    original_text: Mapped[str | None] = mapped_column(Text)
    translation: Mapped[str | None] = mapped_column(Text)
    interpretation: Mapped[str | None] = mapped_column(Text)
    traditional_context: Mapped[str | None] = mapped_column(Text)
    evidence_label: Mapped[str] = mapped_column(String(80), default=EvidenceLevel.TRADITIONAL.value, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    source: Mapped[KnowledgeSource] = relationship(back_populates="ayurvedic_source")


class FoodRegion(Base):
    __tablename__ = "food_regions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    code: Mapped[str | None] = mapped_column(String(30), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class FoodItem(Base):
    __tablename__ = "food_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    local_names: Mapped[list[str]] = mapped_column(JSON, default=list)
    region: Mapped[str | None] = mapped_column(String(80), index=True)
    cuisine: Mapped[str | None] = mapped_column(String(80))
    ingredients: Mapped[list[str]] = mapped_column(JSON, default=list)
    dietary_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    season: Mapped[str | None] = mapped_column(String(40))
    nutrition_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cultural_relevance: Mapped[str | None] = mapped_column(Text)
    pregnancy_context: Mapped[str | None] = mapped_column(Text)
    evidence_status: Mapped[str] = mapped_column(String(40), default=EvidenceLevel.UNCERTAIN.value, nullable=False)
    safety_status: Mapped[str] = mapped_column(String(40), default=SafetyStatus.SAFE_GENERAL.value, nullable=False)
    source_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ExerciseGuidance(Base):
    __tablename__ = "exercise_guidance"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    category: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    suitable_stages: Mapped[list[str]] = mapped_column(JSON, default=list)
    restrictions: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_status: Mapped[str] = mapped_column(String(40), default=EvidenceLevel.UNCERTAIN.value, nullable=False)
    safety_status: Mapped[str] = mapped_column(String(40), default=SafetyStatus.SAFE_GENERAL.value, nullable=False)
    source_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source_documents: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence_level: Mapped[str] = mapped_column(String(40), nullable=False)
    safety_status: Mapped[str] = mapped_column(String(40), nullable=False)
    score: Mapped[float] = mapped_column(default=0.0, nullable=False)
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="recommendations")
    feedback: Mapped[list[Feedback]] = relationship(back_populates="recommendation")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    recommendation_id: Mapped[str | None] = mapped_column(ForeignKey("recommendations.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="feedback")
    message: Mapped[Message | None] = relationship(back_populates="feedback")
    recommendation: Mapped[Recommendation | None] = relationship(back_populates="feedback")

    __table_args__ = (
        CheckConstraint("(message_id IS NOT NULL AND recommendation_id IS NULL) OR (message_id IS NULL AND recommendation_id IS NOT NULL)", name="ck_feedback_one_target"),
    )


class SafetyRule(Base):
    __tablename__ = "safety_rules"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    pattern: Mapped[str] = mapped_column(String(300), nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(40), default=RiskLevel.MEDICAL_REVIEW.value, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(40), default="1", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(160))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class SafetyEvent(Base):
    __tablename__ = "safety_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    matched_rule_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    requested_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    suite: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="running", nullable=False, index=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    report_path: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
