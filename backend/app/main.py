from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import (
    admin,
    auth,
    chat,
    demo,
    evaluations,
    feedback,
    knowledge,
    privacy,
    profile,
    recommendations,
)
from app.api.deps import StaffUser
from app.core.config import get_settings
from app.core.db import SessionLocal, init_db
from app.core.observability import (
    configure_logging,
    log_event,
    metrics,
    new_request_id,
    request_id_context,
)
from app.core.rate_limit import rate_limiter
from app.core.redis import connect_redis
from app.core.security import validate_runtime_security

settings = get_settings()
configure_logging()
logger = logging.getLogger("matriva.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_runtime_security()
    if settings.auto_create_tables:
        init_db()
    app.state.redis = connect_redis()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Evidence-grounded pregnancy education API. Not a diagnostic or emergency-care service.",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def request_security_and_metrics(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", "")[:64] or new_request_id()
    request.state.request_id = request_id
    token = request_id_context.set(request_id)
    started = time.perf_counter()
    path = request.url.path
    try:
        if path.startswith(
            ("/auth", "/chat", "/knowledge", "/sources", "/pregnancy", "/guidelines", "/ayurveda")
        ):
            if path.startswith("/auth"):
                limit = settings.rate_limit_auth_per_minute
            elif path.startswith("/chat"):
                limit = settings.rate_limit_chat_per_minute
            else:
                limit = settings.rate_limit_general_per_minute
            client = request.client.host if request.client else "unknown"
            allowed, _remaining, retry_after = rate_limiter.allow(f"{client}:{path}", limit)
            if not allowed:
                response = JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Rate limit exceeded"},
                    headers={"Retry-After": str(retry_after), "X-Request-ID": request_id},
                )
                metrics.observe(path, (time.perf_counter() - started) * 1000, response.status_code)
                return response
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response
    finally:
        elapsed = (time.perf_counter() - started) * 1000
        metrics.observe(path, elapsed, response.status_code if "response" in locals() else 500)
        request_id_context.reset(token)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    log_event("request.validation_error", request_id=getattr(request.state, "request_id", "-"), path=request.url.path)
    safe_errors = [
        {"loc": list(error.get("loc", [])), "msg": str(error.get("msg", "invalid input")), "type": str(error.get("type", "validation_error"))}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": safe_errors})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled request error request_id=%s", getattr(request.state, "request_id", "-"))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "request_id": getattr(request.state, "request_id", "-")},
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"name": settings.app_name, "version": settings.app_version, "docs": "/docs"}


@app.get("/health")
def health() -> dict[str, str]:
    database_status = "ok"
    redis_status = "ok"
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        database_status = "unavailable"
    redis_client = getattr(app.state, "redis", None)
    if redis_client is not None:
        try:
            redis_client.ping()
        except Exception:  # noqa: BLE001
            redis_status = "unavailable"
    else:
        redis_status = "not_configured"
    overall = "ok" if database_status == "ok" and redis_status in {"ok", "not_configured"} else "degraded"
    return {"status": overall, "database": database_status, "redis": redis_status, "version": settings.app_version}


@app.get("/internal/metrics")
def internal_metrics(_: StaffUser) -> dict[str, object]:
    return metrics.snapshot()


app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(chat.router)
app.include_router(demo.router)
app.include_router(recommendations.router)
app.include_router(knowledge.router)
app.include_router(feedback.router)
app.include_router(privacy.router)
app.include_router(admin.router)
app.include_router(evaluations.router)
