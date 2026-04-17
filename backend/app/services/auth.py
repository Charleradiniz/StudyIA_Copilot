import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from app.config import AUTH_SESSION_TTL_DAYS, PASSWORD_RESET_TOKEN_TTL_MINUTES

PASSWORD_HASH_ITERATIONS = 390000
SESSION_TTL_DAYS = AUTH_SESSION_TTL_DAYS


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )

    return "$".join(
        [
            "pbkdf2_sha256",
            str(PASSWORD_HASH_ITERATIONS),
            base64.urlsafe_b64encode(salt).decode("utf-8"),
            base64.urlsafe_b64encode(digest).decode("utf-8"),
        ]
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_raw, encoded_salt, encoded_digest = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False

        iterations = int(iterations_raw)
        salt = base64.urlsafe_b64decode(encoded_salt.encode("utf-8"))
        expected_digest = base64.urlsafe_b64decode(encoded_digest.encode("utf-8"))
    except Exception:
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual_digest, expected_digest)


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def generate_password_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_session_expiration() -> datetime:
    return utcnow() + timedelta(days=SESSION_TTL_DAYS)


def build_password_reset_expiration() -> datetime:
    return utcnow() + timedelta(minutes=PASSWORD_RESET_TOKEN_TTL_MINUTES)


def is_session_expired(expires_at: datetime | None) -> bool:
    if expires_at is None:
        return True

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return expires_at <= utcnow()
