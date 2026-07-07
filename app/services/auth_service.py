import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from app.core.exceptions import BadRequestError, ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.timeutils import parse_dt
from app.db.container import get_repositories
from app.models.auth import SignupRequest


def _user_public(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "is_premium": user["is_premium"],
    }


def _issue_tokens(user_id: str, family_id: str | None = None) -> dict:
    repos = get_repositories()
    access_token, expires_in = create_access_token(user_id)
    refresh_token, meta = create_refresh_token(user_id, family_id=family_id)
    repos.refresh_tokens.create(
        meta["jti"], user_id, meta["family_id"], meta["expires_at"].isoformat()
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": expires_in,
    }


def signup(payload: SignupRequest) -> dict:
    repos = get_repositories()
    if repos.users.get_by_email(payload.email):
        raise ConflictError("An account with this email already exists")

    fields = payload.model_dump(mode="json")
    user = repos.users.create(
        {
            "email": fields["email"].lower(),
            "password_hash": hash_password(payload.password),
            "display_name": fields["display_name"],
            "dob": fields.get("dob"),
            "gender": fields.get("gender"),
            "reading_preferences": fields.get("reading_preferences") or [],
            "yearly_goal_books": fields.get("yearly_goal_books") or 12,
        }
    )
    tokens = _issue_tokens(user["id"])
    tokens["user"] = _user_public(user)
    return tokens


def login(email: str, password: str) -> dict:
    repos = get_repositories()
    user = repos.users.get_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        raise UnauthorizedError("Invalid email or password")
    tokens = _issue_tokens(user["id"])
    tokens["user"] = _user_public(user)
    return tokens


def refresh(refresh_token: str) -> dict:
    repos = get_repositories()
    try:
        payload = decode_token(refresh_token)
    except Exception as exc:
        raise UnauthorizedError("Refresh token is invalid or expired") from exc

    if payload.get("type") != "refresh":
        raise UnauthorizedError("Refresh token is invalid or expired")

    jti = payload["jti"]
    family = payload["family"]
    user_id = payload["sub"]

    row = repos.refresh_tokens.get(jti)
    if not row:
        raise UnauthorizedError("Refresh token is invalid or expired")
    if row["revoked"]:
        # A previously-rotated token being reused: revoke the whole family.
        repos.refresh_tokens.revoke_family(family)
        raise UnauthorizedError("Refresh token is invalid or expired")

    repos.refresh_tokens.revoke(jti)
    return _issue_tokens(user_id, family_id=family)


def logout(refresh_token: str | None, all_devices: bool, user_id: str) -> None:
    repos = get_repositories()
    if all_devices:
        repos.refresh_tokens.revoke_all_for_user(user_id)
        return
    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            repos.refresh_tokens.revoke(payload["jti"])
        except Exception:
            pass  # idempotent per api-doc.md


def request_password_reset(email: str) -> None:
    repos = get_repositories()
    user = repos.users.get_by_email(email)
    if not user:
        return  # no user enumeration

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(minutes=30)
    repos.password_resets.create(user["id"], token_hash, expires_at.isoformat())
    # Delivery (email/SMS) is out of scope for this backend; the raw `token`
    # would be sent via a transactional email provider here.


def confirm_password_reset(token: str, new_password: str) -> None:
    repos = get_repositories()
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    row = repos.password_resets.get_by_hash(token_hash)
    if not row or row["used"]:
        raise BadRequestError("This reset link is invalid or has expired")
    if parse_dt(row["expires_at"]) < datetime.now(UTC):
        raise BadRequestError("This reset link is invalid or has expired")

    repos.password_resets.mark_used(row["id"])
    repos.users.update(row["user_id"], {"password_hash": hash_password(new_password)})
    repos.refresh_tokens.revoke_all_for_user(row["user_id"])
