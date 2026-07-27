"""Password hashing (bcrypt) and symmetric JWT (HS256) helpers."""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings
from app.exceptions import AuthError

settings = get_settings()

_PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,72}$")


def validate_password_strength(password: str) -> None:
    if not _PASSWORD_RE.match(password):
        raise AuthError(
            "Password must be 8–72 characters and contain at least one letter and one digit."
        )


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:  # malformed hash
        return False


def create_access_token(*, user_id: int, role: str, name: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "name": name,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.resolved_secret(), algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.resolved_secret(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub", "role"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Session expired — please sign in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("Invalid authentication token.") from exc
