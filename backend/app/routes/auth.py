from datetime import datetime, timezone
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.deps import get_current_session, get_current_user, get_db
from app.models.auth_session import AuthSession
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services.auth import (
    build_session_expiration,
    build_password_reset_expiration,
    generate_session_token,
    generate_password_reset_token,
    hash_password,
    hash_session_token,
    is_session_expired,
    normalize_email,
    verify_password,
)
from app.services.email import (
    EmailConfigurationError,
    EmailDeliveryError,
    send_password_reset_email,
)

router = APIRouter(prefix="/auth", tags=["auth"])
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
logger = logging.getLogger("studyiacopilot.auth")


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=8, max_length=128)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=5, max_length=200)


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=20, max_length=400)
    password: str = Field(min_length=8, max_length=128)


def validate_email(email: str) -> str:
    normalized = normalize_email(email)
    if not EMAIL_PATTERN.match(normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter a valid email address.",
        )
    return normalized


def serialize_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "created_at": serialize_datetime(user.created_at),
    }


def resolve_request_origin(request: Request) -> str | None:
    origin = (request.headers.get("origin") or "").strip()
    if origin:
        return origin.rstrip("/")

    base_url = str(request.base_url).strip()
    return base_url.rstrip("/") if base_url else None


def create_user_session(db: Session, user: User) -> tuple[str, AuthSession]:
    token = generate_session_token()
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=build_session_expiration(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return token, session


def build_auth_payload(user: User, token: str, session: AuthSession) -> dict:
    return {
        "token": token,
        "expires_at": serialize_datetime(session.expires_at),
        "user": serialize_user(user),
    }


def create_password_reset_token(db: Session, user: User) -> str:
    invalidate_password_reset_tokens(db, user.id)
    token = generate_password_reset_token()
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=build_password_reset_expiration(),
    )
    db.add(reset_token)
    db.commit()
    db.refresh(reset_token)
    return token


def invalidate_user_sessions(db: Session, user_id: str) -> None:
    db.query(AuthSession).filter(AuthSession.user_id == user_id).delete(
        synchronize_session=False
    )


def invalidate_password_reset_tokens(db: Session, user_id: str) -> None:
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user_id
    ).delete(synchronize_session=False)


@router.post("/register")
def register_user(data: RegisterRequest, db: Session = Depends(get_db)):
    email = validate_email(data.email)
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=email,
        full_name=data.full_name.strip(),
        password_hash=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token, session = create_user_session(db, user)
    return build_auth_payload(user, token, session)


@router.post("/login")
def login_user(data: LoginRequest, db: Session = Depends(get_db)):
    email = validate_email(data.email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token, session = create_user_session(db, user)
    return build_auth_payload(user, token, session)


@router.post("/password-reset/request")
def request_password_reset(
    request: Request,
    data: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    email = validate_email(data.email)
    user = db.query(User).filter(User.email == email).first()

    if user:
        token = create_password_reset_token(db, user)
        try:
            send_password_reset_email(
                recipient_email=user.email,
                recipient_name=user.full_name,
                reset_token=token,
                request_origin=resolve_request_origin(request),
            )
        except EmailConfigurationError as exc:
            db.query(PasswordResetToken).filter(
                PasswordResetToken.token_hash == hash_session_token(token)
            ).delete(synchronize_session=False)
            db.commit()
            logger.warning(
                "password_reset_email_configuration_error user_id=%s email=%s detail=%s",
                user.id,
                user.email,
                str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        except EmailDeliveryError as exc:
            db.query(PasswordResetToken).filter(
                PasswordResetToken.token_hash == hash_session_token(token)
            ).delete(synchronize_session=False)
            db.commit()
            logger.exception(
                "password_reset_email_delivery_error user_id=%s email=%s",
                user.id,
                user.email,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

    return {
        "sent": True,
        "message": (
            "If the email exists in our workspace, a password reset link has been sent."
        ),
    }


@router.post("/password-reset/confirm")
def confirm_password_reset(
    data: PasswordResetConfirmRequest,
    db: Session = Depends(get_db),
):
    token_hash = hash_session_token(data.token)
    reset_token = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .first()
    )

    if not reset_token or reset_token.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link is invalid or has already been used.",
        )

    if is_session_expired(reset_token.expires_at):
        db.delete(reset_token)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link has expired.",
        )

    user = db.query(User).filter(User.id == reset_token.user_id).first()
    if not user:
        db.delete(reset_token)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user for this password reset link was not found.",
        )

    user.password_hash = hash_password(data.password)
    invalidate_user_sessions(db, user.id)
    invalidate_password_reset_tokens(db, user.id)
    db.commit()

    return {
        "password_reset": True,
        "message": "Password updated. You can sign in with the new password now.",
    }


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"user": serialize_user(current_user)}


@router.post("/logout")
def logout_user(
    session: AuthSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    db.delete(session)
    db.commit()
    return {"logged_out": True}
