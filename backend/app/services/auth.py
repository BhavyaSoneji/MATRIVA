from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, utc_now, verify_password
from app.models import User, UserRole
from app.schemas.api import LoginRequest, RegisterRequest


class AuthError(ValueError):
    pass


def register_user(db: Session, data: RegisterRequest) -> User:
    email = data.email.lower().strip()
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        raise AuthError("An account with this email already exists")
    user = User(
        email=email,
        password_hash=hash_password(data.password),
        full_name=data.full_name.strip() if data.full_name else None,
        role=UserRole.USER.value,
        is_active=True,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AuthError("An account with this email already exists") from exc
    return user


def authenticate_user(db: Session, data: LoginRequest) -> User:
    user = db.execute(select(User).where(User.email == data.email.lower().strip())).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(data.password, user.password_hash):
        raise AuthError("Invalid email or password")
    user.last_login_at = utc_now()
    db.flush()
    return user


def user_payload(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }
