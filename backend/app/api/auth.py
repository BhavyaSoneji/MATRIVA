from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DBSession
from app.core.config import get_settings
from app.core.security import create_access_token
from app.schemas.api import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth import AuthError, authenticate_user, register_user, user_payload

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DBSession) -> TokenResponse:
    try:
        user = register_user(db, payload)
        db.commit()
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return TokenResponse(
        access_token=create_access_token(user),
        expires_in=get_settings().jwt_expires_minutes * 60,
        user=UserResponse.model_validate(user_payload(user)),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DBSession) -> TokenResponse:
    try:
        user = authenticate_user(db, payload)
        db.commit()
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password") from exc
    return TokenResponse(
        access_token=create_access_token(user),
        expires_in=get_settings().jwt_expires_minutes * 60,
        user=UserResponse.model_validate(user_payload(user)),
    )


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user_payload(user))
