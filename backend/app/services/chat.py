from __future__ import annotations

import json
import time
from collections.abc import Generator, Iterable
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.observability import log_event
from app.core.security import hash_for_log
from app.llm.generator import GenerationResult
from app.models import (
    Conversation,
    DietaryProfile,
    Message,
    MessageRole,
    PregnancyProfile,
    SafetyStatus,
    User,
)
from app.rag.pipeline import answer_question, answer_question_stream
from app.rag.retrieval import RetrievedChunk
from app.repositories.knowledge import source_payload
from app.safety.classifier import (
    SafetyDecision,
    SafetySubsystemError,
    classify_query,
    insufficient_evidence,
    validate_generated_answer,
)
from app.schemas.api import (
    ChatResponse,
    Citation,
    MessageRequest,
    RecommendationResponse,
    SourceResponse,
)
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


def _run_safety_pre_check(db: Session, payload: MessageRequest, user: User | None) -> tuple[str, SafetyDecision]:
    """Shared by `process_chat` and `stream_chat`: intent classification plus
    the Section 19/20 safety pre-check (`classify_query`), which MUST run --
    and, for urgent/high-risk queries, MUST short-circuit -- before any
    retrieval, web search, or LLM call in either the blocking or the
    streaming endpoint. Raises `SafetySubsystemError` (fail closed) exactly
    like the non-streaming path always has, rather than letting a broken
    classifier silently let a query through.
    """
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
    return intent, decision


@dataclass
class _FinalizedAnswer:
    answer: str
    safety_status: Any
    citations: list[Citation]
    corrected: bool  # True iff `answer` differs from the raw `generation.text` (post-check replaced it)


def _finalize_generation_result(
    generation: GenerationResult,
    chunks: list[RetrievedChunk],
    decision: SafetyDecision,
    *,
    request_id: str,
) -> _FinalizedAnswer:
    """Shared by `process_chat` and `stream_chat`: turns a `GenerationResult`
    (whatever produced it -- blocking `answer_question` or a fully-buffered
    streamed answer from `answer_question_stream`) into the final answer
    text, safety_status, and citation list. This is the ONE place the
    Section 21-equivalent post-check (`validate_generated_answer`) runs for
    the live chat path -- neither caller may skip it.

    `generation.text` (not just `chunks`) is the real "do we have anything
    to say" signal: when Tavily is configured, a web-grounded answer can
    exist with zero local `chunks` -- checking `chunks` alone would silently
    discard that answer and always fall back to insufficient_evidence().
    """
    if not generation.text:
        return _FinalizedAnswer(
            answer=insufficient_evidence(),
            safety_status=SafetyStatus.INSUFFICIENT_INFORMATION,
            citations=[],
            corrected=False,
        )

    web_citations = generation.web_citations
    post_check = validate_generated_answer(
        generation.text,
        source_ids=[item.source.id for item in chunks] + [web.web_id for web in web_citations],
        citation_ids=generation.citation_ids,
        decision=decision,
        require_source=True,
    )
    if post_check.valid:
        citations = [
            Citation(
                source_id=item.source.id,
                source_name=item.source.name,
                locator=item.source.extra_metadata.get("page_or_section") if item.source.extra_metadata else None,
                evidence_level=item.source.evidence_level,
            )
            for item in chunks[:4]
        ]
        # External web results are appended as their own, distinctly-labeled
        # citations (source_type="external_web", evidence_level="uncertain",
        # real url+domain) -- never merged into or mistaken for the
        # reviewed local citations above.
        citations += [
            Citation(
                source_id=web.web_id,
                source_name=web.title,
                locator=web.url,
                evidence_level=web.evidence_level,
                source_type=web.source_type,
                url=web.url,
                domain=web.domain,
            )
            for web in web_citations
        ]
        return _FinalizedAnswer(
            answer=generation.text, safety_status=decision.status, citations=citations, corrected=False
        )

    answer = post_check.safe_answer or insufficient_evidence()
    safety_status = SafetyStatus.MEDICAL_REVIEW if decision.risk.value == "medical_review" else SafetyStatus.INSUFFICIENT_INFORMATION
    log_event("chat.post_check_failed", request_id=request_id, reason=post_check.reason)
    return _FinalizedAnswer(answer=answer, safety_status=safety_status, citations=[], corrected=True)


def process_chat(
    db: Session,
    payload: MessageRequest,
    *,
    user: User | None,
    request_id: str,
) -> ChatResponse:
    intent, decision = _run_safety_pre_check(db, payload, user)
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
        if generation.text:
            generation_latency_ms = retrieval_latency_ms
        finalized = _finalize_generation_result(generation, chunks, decision, request_id=request_id)
        answer = finalized.answer
        safety_status = finalized.safety_status
        citations = finalized.citations

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
        "web_search_used": any(c.source_type == "external_web" for c in citations),
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


def format_sse_event(event: str, data: dict[str, Any]) -> str:
    """Render one Server-Sent Events frame: `event: <type>\\ndata: <json>\\n\\n`.

    Used by both `stream_chat` (below) and `app.api.chat`'s error handling,
    so a stream that fails after headers are already sent (see that module)
    still emits a frame in exactly the same wire format as every other event
    in the stream, instead of a bare/differently-shaped error payload.
    """
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def stream_chat(
    db: Session,
    payload: MessageRequest,
    *,
    user: User | None,
    request_id: str,
) -> Generator[str, None, None]:
    """SSE generator backing POST /chat/stream.

    WIRE FORMAT -- a frontend consumer (fetch + ReadableStream, or EventSource)
    must parse exactly this; each frame is standard SSE framing,
    `event: <type>\\ndata: <json>\\n\\n`:

    - "delta"  {"text": str} -- append `text` to the growing displayed
      answer. Zero or more of these arrive before "final". For a safety
      short-circuit, or when no live model is configured, exactly ONE
      "delta" carries the ENTIRE fixed answer as one piece (there is no
      live model call to stream tokens from in either case).
    - "final"  {"answer": str, "safety_status": str, "citations": [...],
      "corrected": bool} -- sent exactly once, after the complete answer has
      gone through citation validation and the safety post-check (Section
      21/Section 43 grounding, same as process_chat). `citations` has the
      same shape as `ChatResponse.citations` (local citations, then any
      "source_type": "external_web" citations). If `corrected` is true, the
      post-check replaced the raw streamed text (e.g. it failed validation)
      -- the frontend MUST discard/replace whatever it rendered from "delta"
      events with `answer` here, never merge/append it. If `corrected` is
      false, `answer` is exactly the concatenation of every prior "delta"
      event's `text`.
    - "done"  {"conversation_id": str, "message_id": str, "sources": [...],
      "evidence": {...}, "recommendations": [...]} -- sent last, once the
      conversation/message rows are persisted; mirrors the remaining
      `ChatResponse` fields that aren't part of the visible answer text.
      Never changes what's displayed -- purely metadata.
    - "error"  {"answer": str} -- emitted instead of the above by
      `app.api.chat`'s wrapper if the safety subsystem is unavailable or an
      unexpected server error occurs after the stream has already started
      (mirrors non-streaming /chat's 503 body's `answer` field); the stream
      ends immediately after.

    Reuses the EXACT SAME safety pre-check (`_run_safety_pre_check`),
    retrieval/grounding/web-search (`answer_question_stream`, which itself
    is `answer_question`'s streaming counterpart), and citation-validation +
    safety post-check (`_finalize_generation_result`) as `process_chat` --
    the ONLY difference is that generation streams tokens instead of
    returning a complete string in one call. Persistence (conversation +
    message rows, recommendations) happens once, after the full answer text
    and final safety_status/citations are known, exactly like
    `process_chat` -- just emitted via the "done" event instead of being
    part of a single JSON response.
    """
    intent, decision = _run_safety_pre_check(db, payload, user)
    stage, region = _profile_context(db, user)
    sources: list[SourceResponse] = []
    citations: list[Citation] = []
    recommendations: list[Any] = []
    retrieval_latency_ms = 0.0
    generation_latency_ms = 0.0

    if decision.risk.value in {"urgent_escalation", "high_risk"}:
        # Section 20: safety short-circuit -- exactly like process_chat, the
        # LLM/retrieval/web-search are never invoked at all for this query.
        answer = decision.response or "Please contact a qualified maternity-care professional for an urgent review."
        safety_status = decision.status
        yield format_sse_event("delta", {"text": answer})
        yield format_sse_event(
            "final",
            {"answer": answer, "safety_status": safety_status.value, "citations": [], "corrected": False},
        )
    else:
        retrieval_started = time.perf_counter()
        chunks: list[RetrievedChunk] = []
        final_generation: GenerationResult | None = None
        streamed_parts: list[str] = []
        for stream_event in answer_question_stream(db, payload.message, stage=stage, region=region):
            if stream_event.kind == "delta":
                streamed_parts.append(stream_event.text)
                yield format_sse_event("delta", {"text": stream_event.text})
            else:
                final_generation = stream_event.generation
                chunks = stream_event.chunks
        retrieval_latency_ms = round((time.perf_counter() - retrieval_started) * 1000, 2)
        sources = _unique_sources(chunks)
        generation = final_generation or GenerationResult(text="", citation_ids=[])
        if generation.text:
            generation_latency_ms = retrieval_latency_ms
        finalized = _finalize_generation_result(generation, chunks, decision, request_id=request_id)
        answer = finalized.answer
        safety_status = finalized.safety_status
        citations = finalized.citations
        # Some branches of answer_question_stream (zero local evidence and no
        # Tavily configured) have nothing to stream and emit only a "final"
        # marker with empty text -- the real answer (insufficient_evidence())
        # is only computed here, after the loop. Per the documented wire
        # contract every query gets at least one "delta" before "final", so
        # the frontend never has to special-case "zero deltas arrived":
        # synthesize one covering the whole answer, exactly like the
        # safety-short-circuit and no-key branches already do explicitly.
        if not streamed_parts and answer:
            yield format_sse_event("delta", {"text": answer})
            streamed_parts.append(answer)
        # `corrected` is true whenever the authoritative final answer isn't
        # exactly what was streamed -- either because the post-check
        # replaced it (finalized.corrected) or because generation produced
        # nothing at all and insufficient_evidence() was substituted.
        streamed_text = "".join(streamed_parts)
        corrected = finalized.corrected or answer != streamed_text
        yield format_sse_event(
            "final",
            {
                "answer": answer,
                "safety_status": safety_status.value if hasattr(safety_status, "value") else safety_status,
                "citations": [item.model_dump(mode="json") for item in citations],
                "corrected": corrected,
            },
        )

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
        "web_search_used": any(item.source_type == "external_web" for item in citations),
        "request_id": request_id,
        "user_message_id": user_message.id,
    }
    log_event(
        "chat.completed",
        request_id=request_id,
        intent=intent,
        safety_status=safety_status.value if hasattr(safety_status, "value") else safety_status,
        retrieval_count=len(sources),
        source_count=len(sources),
    )
    yield format_sse_event(
        "done",
        {
            "conversation_id": conversation.id,
            "message_id": assistant_message.id,
            "sources": [item.model_dump(mode="json") for item in sources],
            "evidence": evidence,
            "recommendations": [
                RecommendationResponse.model_validate(item).model_dump(mode="json") for item in recommendations
            ],
        },
    )
