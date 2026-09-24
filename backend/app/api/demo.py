from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.api import NextVisitResponse

router = APIRouter(tags=["demo"])

ANC_CONTACT_WEEKS = (12, 20, 26, 30, 34, 36, 38, 40, 41)


@router.get("/pregnancy/next-visit", response_model=NextVisitResponse)
def next_visit(current_week: int = Query(default=18, ge=1, le=42)) -> NextVisitResponse:
    next_week = next((week for week in ANC_CONTACT_WEEKS if week >= current_week), None)
    if next_week is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The configured contact schedule has no next visit at or after this week",
        )
    return NextVisitResponse(
        next_visit_week=next_week,
        current_week=current_week,
        message=f"Your next check-up is coming up around week {next_week}. Please confirm timing and any instructions with your maternity-care professional.",
        source_id="fogsi-anc-contact-schedule",
        evidence_level="supported",
    )
