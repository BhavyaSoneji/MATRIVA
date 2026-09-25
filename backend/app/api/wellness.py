from datetime import date as date_type
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession
from app.schemas.api import (
    WellnessLogRequest,
    WellnessLogResponse,
    WellnessSummaryResponse,
)
from app.services.wellness import get_daily_log, get_summary, upsert_daily_log

router = APIRouter(prefix="/wellness", tags=["wellness"])


@router.put("/daily", response_model=WellnessLogResponse)
def put_daily_wellness(payload: WellnessLogRequest, user: CurrentUser, db: DBSession) -> WellnessLogResponse:
    log = upsert_daily_log(db, user, payload)
    db.commit()
    return WellnessLogResponse(
        date=log.log_date,
        water_intake_ml=log.water_intake_ml,
        sleep_hours=log.sleep_hours,
        activity_minutes=log.activity_minutes,
        updated_at=log.updated_at,
    )


@router.get("/daily", response_model=WellnessLogResponse)
def get_daily_wellness(
    user: CurrentUser,
    db: DBSession,
    date: Annotated[date_type | None, Query()] = None,
) -> WellnessLogResponse:
    target_date = date or datetime.now(timezone.utc).date()
    log = get_daily_log(db, user, target_date)
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No wellness log for this date")
    return WellnessLogResponse(
        date=log.log_date,
        water_intake_ml=log.water_intake_ml,
        sleep_hours=log.sleep_hours,
        activity_minutes=log.activity_minutes,
        updated_at=log.updated_at,
    )


@router.get("/summary", response_model=WellnessSummaryResponse)
def get_wellness_summary(user: CurrentUser, db: DBSession, days: int = Query(default=7, ge=1, le=30)) -> WellnessSummaryResponse:
    logs = get_summary(db, user, days)
    return WellnessSummaryResponse(
        days=[
            WellnessLogResponse(
                date=log.log_date,
                water_intake_ml=log.water_intake_ml,
                sleep_hours=log.sleep_hours,
                activity_minutes=log.activity_minutes,
                updated_at=log.updated_at,
            )
            for log in logs
        ]
    )
