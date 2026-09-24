import base64
import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models import User, UserRole

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

_PBKDF2_ITERATIONS = 310_000
_PASSWORD_PREFIX = "pbkdf2_sha256"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 and a random salt."""

    if len(password) < 12:
        raise ValueError("password must be at least 12 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    def encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    return f"{_PASSWORD_PREFIX}${_PBKDF2_ITERATIONS}${encode(salt)}${encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != _PASSWORD_PREFIX:
            return False
        iterations = int(iterations_text)
        if iterations < 100_000 or iterations > 2_000_000:
            return False
        def decode(value: str) -> bytes:
            return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

        salt = decode(salt_text)
        expected = decode(digest_text)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError, IndexError):
        return False


def create_access_token(user: User) -> str:
    now = utc_now()
    expires = now + timedelta(minutes=settings.jwt_expires_minutes)
    payload: dict[str, Any] = {
        "sub": user.id,
        "role": user.role.value if isinstance(user.role, UserRole) else str(user.role),
        "type": "access",
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": expires,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    if not token or len(token) > 4096:
        raise credentials_exception()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "exp", "iat", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise credentials_exception() from exc
    if payload.get("type") != "access" or not isinstance(payload.get("sub"), str):
        raise credentials_exception()
    return payload


def credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),  # noqa: B008
) -> User:
    if not token:
        raise credentials_exception()
    payload = decode_access_token(token)
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise credentials_exception()
    return user


def get_optional_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),  # noqa: B008
) -> User | None:
    if not token:
        return None
    payload = decode_access_token(token)
    user = db.get(User, payload["sub"])
    return user if user and user.is_active else None


def require_admin(user: User = Depends(get_current_user)) -> User:  # noqa: B008
    role = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    if role not in {UserRole.ADMIN.value, UserRole.EVALUATOR.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff privileges required")
    return user


def require_admin_only(user: User = Depends(get_current_user)) -> User:  # noqa: B008
    role = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    if role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator privileges required")
    return user


def sanitize_filename(filename: str | None) -> str:
    if not filename:
        return "upload"
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name[:180] or "upload"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hash_for_log(value: str) -> str:
    """Hash sensitive text before it enters logs or safety-event records."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def validate_runtime_security() -> None:
    if settings.is_production:
        secret_lower = settings.jwt_secret.lower()
        if (
            settings.jwt_secret == "dev-only-change-me-please-use-32-plus-chars"
            or len(settings.jwt_secret) < 32
            or "replace-with" in secret_lower
            or "change-me" in secret_lower
        ):
            raise RuntimeError("JWT_SECRET must be a unique value of at least 32 characters in production")
        if settings.demo_mode:
            raise RuntimeError("DEMO_MODE must be false in production")
        if settings.debug:
            raise RuntimeError("DEBUG must be false in production")
        if "*" in settings.cors_origin_list:
            raise RuntimeError("CORS_ORIGINS must not contain * in production")
