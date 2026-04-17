from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import AUTH_SESSION_COOKIE_NAME
from app.db import database
from app.models.auth_session import AuthSession
from app.models.user import User
from app.services.auth import hash_session_token, is_session_expired

security = HTTPBearer(auto_error=False)


def get_db():
    if database.SessionLocal is None:
        raise RuntimeError("Database session factory is not configured.")

    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_session(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db=Depends(get_db),
):
    raw_token = (request.cookies.get(AUTH_SESSION_COOKIE_NAME) or "").strip() or None
    if not raw_token and credentials is not None and credentials.scheme.lower() == "bearer":
        raw_token = credentials.credentials

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    token_hash = hash_session_token(raw_token)
    session = db.query(AuthSession).filter(AuthSession.token_hash == token_hash).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )

    if is_session_expired(session.expires_at):
        db.delete(session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token expired.",
        )

    return session


def get_current_user(
    session: AuthSession = Depends(get_current_session),
    db=Depends(get_db),
):
    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user not found.",
        )

    return user
