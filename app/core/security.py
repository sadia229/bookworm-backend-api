import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _encode(payload: dict) -> str:
    settings = get_settings()
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError subclasses on invalid/expired tokens."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def create_access_token(user_id: str) -> tuple[str, int]:
    settings = get_settings()
    expires_in = settings.access_token_expire_minutes * 60
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return _encode(payload), expires_in


def create_refresh_token(user_id: str, family_id: str | None = None) -> tuple[str, dict[str, Any]]:
    """Returns (token, meta) where meta has jti/family_id/expires_at for the DB row."""
    settings = get_settings()
    now = datetime.now(UTC)
    jti = str(uuid.uuid4())
    family = family_id or str(uuid.uuid4())
    expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "jti": jti,
        "family": family,
        "iat": int(now.timestamp()),
        "exp": expires_at,
    }
    token = _encode(payload)
    return token, {
        "jti": jti,
        "family_id": family,
        "user_id": user_id,
        "expires_at": expires_at,
    }
