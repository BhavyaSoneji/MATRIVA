from __future__ import annotations

from collections.abc import Iterable
import time
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.observability import log_event
from app.core.security import hash_for_log
from app.models import (
    Conversation,
    DietaryProfile,
    Message,
    MessageRole,
    PregnancyProfile,
    SafetyStatus,
    User,
)
from app.rag.pipeline import answer_question
from app.rag.retrieval import RetrievedChunk
from app.repositories.knowledge import source_payload
from app.safety.classifier import SafetySubsystemError, classify_query, insufficient_evidence, validate_generated_answer
from app.schemas.api import ChatResponse, Citation, MessageRequest, SourceResponse
from app.services.audit import active_safety_rules, record_safety_event
from app.services.recommendation import generate_recommendations
from app.services.stage import calculate_stage


INTENT_KEYWORDS = {
    "EMERGENCY": {"emergency", "bleeding", "severe headache", "fetal movement", "breathing", "pain"},
    "MEDICATION": {"medication", "tablet", "dose", "prescription", "antibiotic"},
    "NUTRITION": {"food", "eat", "diet", "nutrition", "vitamin", "supplement"},
    "EXERCISE": {"exercise", "workout", "walk", "yoga", "physical activity"},
    "LIFESTYLE": {"sleep", "travel", "stress", "routine", "meditation"},
    "ANTENATAL_CARE": {"anc", "check-up", "checkup", "visit", "doctor", "clinic"},
    "AYURVEDA": {"ayurveda", "garbhini", "traditional", "verse"},
    "PREGNANCY_DEVELOPMENT": {"week", "trimester", "development", "due date"},
}


def classify_intent(message: str) -> str:
    normalized = message.lower()
    scores = {intent: sum(1 for keyword in keywords if keyword in normalized) for intent, keywords in INTENT_KEYWORDS.items()}
    intent, score = max(scores.items(), key=lambda item: item[1])
    return intent if score else "GENERAL"


def _unique_sources(chunks: Iterable[RetrievedChunk]) -> list[SourceResponse]:
    seen: set[str] = set()
    result: list[SourceResponse] = []
    for item in chunks:
        if item.source.id in seen:
            continue
        seen.add(item.source.id)
        result.append(SourceResponse.model_validate(source_payload(item.source)))
    return result


def _profile_context(db: Session, user: User | None) -> tuple[str | None, str | None]:
    if user is None:
        return None, None
    pregnancy = db.execute(select(PregnancyProfile).where(PregnancyProfile.user_id == user.id)).scalar_one_or_none()
    dietary = db.execute(select(DietaryProfile).where(DietaryProfile.user_id == user.id)).scalar_one_or_none()
    stage = calculate_stage(pregnancy.current_week).stage if pregnancy else None
    return stage, dietary.region if dietary else None


def _conversation(db: Session, user: User | None, payload: MessageRequest) -> Conversation:
    if payload.conversation_id:
        conversation = db.get(Conversation, payload.conversation_id)
        if conversation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        if user is not None and conversation.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Conversation does not belong to this user")
        if user is None and conversation.user_id is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Conversation is not available in demo mode")
        return conversation
    conversation = Conversation(user_id=user.id if user else None, session_context=payload.session_context)
    db.add(conversation)
    db.flush()
    return conversation


def _add_message(
    db: Session,
    conversation: Conversation,
    *,
    user: User | None,
    role: str,
    content: str,
    intent: str | None = None,
    safety_status: str | None = None,
    citations: list[dict[str, Any]] | None = None,
    sources: list[dict[str, Any]] | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        user_id=user.id if user else None,
        role=role,
        content=content,
        intent=intent,
        safety_status=safety_status,
        citations=citations or [],
        sources=sources or [],
    )
    db.add(message)
    db.flush()
    return message


def process_chat(
    db: Session,
    payload: MessageRequest,
    *,
    user: User | None,
    request_id: str,
) -> ChatResponse:
    intent = classify_intent(payload.message)
    try:
        rules = active_safety_rules(db)
        decision = classify_query(payload.message, rules)
    except Exception as exc:
        raise SafetySubsystemError("safety pre-check unavailable") from exc
    if decision.risk.value != "safe_general":
        record_safety_event(
            db,
            user_id=user.id if user else None,
            query_hash=hash_for_log(payload.message),
            risk_level=decision.risk.value,
            matched_rule_ids=decision.matched_rule_ids,
            action="pre_check",
        )

    stage, region = _profile_context(db, user)
    sources: list[SourceResponse] = []
    citations: list[Citation] = []
    recommendations = []
    retrieval_latency_ms = 0.0
    generation_latency_ms = 0.0
    if decision.risk.value in {"urgent_escalation", "high_risk"}:
        answer = decision.response or "Please contact a qualified maternity-care professional for an urgent review."
        safety_status = decision.status
    else:
        retrieval_started = time.perf_counter()
        generation, chunks = answer_question(db, payload.message, stage=stage, region=region)
        retrieval_latency_ms = round((time.perf_counter() - retrieval_started) * 1000, 2)
        sources = _unique_sources(chunks)
        if not chunks:
            answer = insufficient_evidence()
            safety_status = SafetyStatus.INSUFFICIENT_INFORMATION
        else:
            generation_latency_ms = retrieval_latency_ms
            post_check = validate_generated_answer(
                generation.text,
                source_ids=[item.source.id for item in chunks],
                citation_ids=generation.citation_ids,
                decision=decision,
                require_source=True,
            )
            if post_check.valid:
                answer = generation.text
                safety_status = decision.status
                citations = [
                    Citation(
                        source_id=item.source.id,
                        source_name=item.source.name,
                        locator=item.source.extra_metadata.get("page_or_section") if item.source.extra_metadata else None,
                        evidence_level=item.source.evidence_level,
                    )
                    for item in chunks[:4]
                ]
            else:
                answer = post_check.safe_answer or insufficient_evidence()
                safety_status = SafetyStatus.MEDICAL_REVIEW if decision.risk.value == "medical_review" else SafetyStatus.INSUFFICIENT_INFORMATION
                log_event("chat.post_check_failed", request_id=request_id, reason=post_check.reason)

    conversation = _conversation(db, user, payload)
    user_message = _add_message(
        db,
        conversation,
        user=user,
        role=MessageRole.USER.value,
        content=payload.message,
        intent=intent,
        safety_status=safety_status,
    )
    assistant_message = _add_message(
        db,
        conversation,
        user=user,
        role=MessageRole.ASSISTANT.value,
        content=answer,
        intent=intent,
        safety_status=safety_status,
        citations=[item.model_dump(mode="json") for item in citations],
        sources=[item.model_dump(mode="json") for item in sources],
    )

    if user is not None and stage:
        recommendations = generate_recommendations(db, user, intent=intent, limit=3)

    evidence = {
        "source_count": len(sources),
        "retrieval_count": 0 if not sources else len(sources),
        "retrieval_latency_ms": retrieval_latency_ms,
        "generation_latency_ms": generation_latency_ms,
        "safety_reason": decision.reason,
        "citation_validation": "passed" if citations else "not_applicable",
        "request_id": request_id,
    }
    log_event(
        "chat.completed",
        request_id=request_id,
        intent=intent,
        safety_status=safety_status.value if hasattr(safety_status, "value") else safety_status,
        retrieval_count=len(sources),
        source_count=len(sources),
    )
    response = ChatResponse(
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        answer=answer,
        intent=intent,
        safety_status=safety_status.value if hasattr(safety_status, "value") else safety_status,
        sources=sources,
        citations=citations,
        evidence=evidence,
        recommendations=[item for item in recommendations],
    )
    # Keep the user message ID available for feedback without exposing it in logs.
    response.evidence["user_message_id"] = user_message.id
    return response
