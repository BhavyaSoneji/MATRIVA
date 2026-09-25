from collections.abc import Generator

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, OptionalUser
from app.core.config import get_settings
from app.core.observability import log_event
from app.models import Conversation, Message
from app.safety.classifier import SafetySubsystemError
from app.schemas.api import ChatHistoryResponse, ChatResponse, MessageRequest
from app.services.chat import format_sse_event, process_chat, stream_chat

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(payload: MessageRequest, request: Request, user: OptionalUser, db: DBSession) -> ChatResponse | JSONResponse:
    if user is None and not get_settings().demo_mode:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required")
    try:
        response = process_chat(db, payload, user=user, request_id=getattr(request.state, "request_id", "-"))
        db.commit()
        return response
    except HTTPException:
        db.rollback()
        raise
    except SafetySubsystemError as exc:
        db.rollback()
        log_event("chat.safety_subsystem_failed", request_id=getattr(request.state, "request_id", "-"), reason=str(exc))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "answer": "I cannot safely process this question because the safety service is unavailable. Please contact a qualified maternity-care professional; for urgent symptoms, contact your local emergency service.",
                "intent": "SAFETY_UNAVAILABLE",
                "safety_status": "medical_review",
                "sources": [],
                "citations": [],
                "evidence": {"citation_validation": "blocked", "safety_subsystem": "unavailable"},
                "recommendations": [],
            },
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        log_event("chat.dependency_failed", request_id=getattr(request.state, "request_id", "-"), error_type=type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "answer": "I cannot safely complete this request right now. Please try again later or contact a qualified maternity-care professional.",
                "intent": "SERVICE_UNAVAILABLE",
                "safety_status": "medical_review",
                "sources": [],
                "citations": [],
                "evidence": {"citation_validation": "blocked"},
                "recommendations": [],
            },
        )


@router.post("/chat/stream")
def chat_stream(payload: MessageRequest, request: Request, user: OptionalUser, db: DBSession) -> StreamingResponse:
    """Streaming counterpart to POST /chat.

    Runs the exact same pipeline as /chat (safety pre-check, retrieval,
    Section 43 grounding/web-search, citation validation, safety
    post-check) via `app.services.chat.stream_chat` -- the only difference
    is that the LLM's tokens are forwarded to the client as they arrive
    instead of the whole response being buffered and returned at once.

    Response is `text/event-stream` (Server-Sent Events). See
    `app.services.chat.stream_chat`'s docstring for the exact frame shapes
    ("delta"/"final"/"done"/"error") a frontend consumer must parse -- that
    docstring is the authoritative wire-format contract for this endpoint.
    """
    if user is None and not get_settings().demo_mode:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required")
    request_id = getattr(request.state, "request_id", "-")

    def event_source() -> Generator[str, None, None]:
        try:
            yield from stream_chat(db, payload, user=user, request_id=request_id)
            db.commit()
        except SafetySubsystemError as exc:
            db.rollback()
            log_event("chat.safety_subsystem_failed", request_id=request_id, reason=str(exc))
            yield format_sse_event(
                "error",
                {
                    "answer": (
                        "I cannot safely process this question because the safety service is "
                        "unavailable. Please contact a qualified maternity-care professional; for "
                        "urgent symptoms, contact your local emergency service."
                    )
                },
            )
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            log_event("chat.dependency_failed", request_id=request_id, error_type=type(exc).__name__)
            yield format_sse_event(
                "error",
                {
                    "answer": (
                        "I cannot safely complete this request right now. Please try again later or "
                        "contact a qualified maternity-care professional."
                    )
                },
            )

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/chat/history", response_model=ChatHistoryResponse)
def chat_history(
    user: CurrentUser,
    db: DBSession,
    conversation_id: str = Query(..., min_length=1, max_length=64),
) -> ChatHistoryResponse:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    messages = db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    ).scalars().all()
    return ChatHistoryResponse(
        conversation_id=conversation.id,
        messages=[
            {
                "id": item.id,
                "role": item.role,
                "content": item.content,
                "intent": item.intent,
                "safety_status": item.safety_status,
                "citations": item.citations,
                "created_at": item.created_at.isoformat(),
            }
            for item in messages
        ],
    )
