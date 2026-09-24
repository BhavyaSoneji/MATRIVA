from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DBSession, StaffUser
from app.models import EvaluationRun
from app.schemas.api import EvaluationRequest, EvaluationResponse
from app.services.evaluation import run_evaluation

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/run", response_model=EvaluationResponse)
def trigger_evaluation(payload: EvaluationRequest, admin: StaffUser, db: DBSession) -> EvaluationResponse:
    run = run_evaluation(db, admin, payload.suite)
    db.commit()
    return EvaluationResponse.model_validate(run)


@router.get("/results", response_model=list[EvaluationResponse])
def list_results(
    admin: StaffUser,
    db: DBSession,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[EvaluationResponse]:
    runs = db.execute(select(EvaluationRun).order_by(EvaluationRun.started_at.desc()).limit(limit)).scalars().all()
    return [EvaluationResponse.model_validate(item) for item in runs]


@router.get("/results/{run_id}", response_model=EvaluationResponse)
def get_result(run_id: str, admin: StaffUser, db: DBSession) -> EvaluationResponse:
    run = db.get(EvaluationRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found")
    return EvaluationResponse.model_validate(run)
