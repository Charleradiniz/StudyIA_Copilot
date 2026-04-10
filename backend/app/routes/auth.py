from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.deps import get_current_session, get_current_user, get_db
from app.models.auth_session import AuthSession
from app.models.user import User
from app.services.auth import (
    build_session_expiration,
    generate_session_token,
    hash_password,
    hash_session_token,
    normalize_email,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=200)
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
