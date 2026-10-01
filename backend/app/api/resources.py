from __future__ import annotations

from fastapi import APIRouter, Query, Response

from app.api.deps import CurrentUser
from app.schemas.api import ResourceLibraryResponse, ResourceResponse
from app.services.resources import search_resources, topics, verified_on

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("", response_model=ResourceLibraryResponse)
def list_resources(
    response: Response,
    _: CurrentUser,
    q: str = Query(default="", max_length=500),
    topic: str | None = Query(default=None, max_length=40),
    type: str | None = Query(default=None, pattern="^(video|article|guideline|research)$"),
    stage: str | None = Query(default=None, max_length=20),
    language: str | None = Query(default=None, max_length=8),
    limit: int = Query(default=12, ge=1, le=60),
) -> ResourceLibraryResponse:
    # The library only changes when build_library.py is re-run, so let the browser reuse it briefly.
    response.headers["Cache-Control"] = "private, max-age=300"
    items = search_resources(
        query=q, topic=topic, resource_type=type, stage=stage, language=language, limit=limit
    )
    return ResourceLibraryResponse(
        verified_on=verified_on(),
        topics=topics(),
        resources=[ResourceResponse(**item) for item in items],
    )
