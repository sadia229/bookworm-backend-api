from app.core.exceptions import BadRequestError, NotFoundError
from app.core.timeutils import iso
from app.db.container import get_repositories
from app.models.users import UpdateProfileRequest
from app.services import storage_service


def _serialize_full(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "name_hidden": user["name_hidden"],
        "phone": user.get("phone"),
        "avatar_id": user.get("avatar_id"),
        "avatar_url": user.get("avatar_url"),
        "gender": user.get("gender"),
        "dob": (
            user.get("dob").isoformat()
            if hasattr(user.get("dob"), "isoformat")
            else user.get("dob")
        ),
        "reading_preferences": user.get("reading_preferences") or [],
        "points": user["points"],
        "books_completed": user["books_completed"],
        "world_stage": user["world_stage"],
        "is_premium": user["is_premium"],
        "premium_until": iso(user.get("premium_until")),
        "daily_goal_pages": user.get("daily_goal_pages", 10),
        "yearly_goal_books": user.get("yearly_goal_books", 12),
        "reminder_time": user.get("reminder_time", "20:00"),
        "created_at": iso(user["created_at"]),
        "updated_at": iso(user["updated_at"]),
    }


def _serialize_public(user: dict) -> dict:
    display_name = "Anonymous Reader" if user["name_hidden"] else user["display_name"]
    return {
        "id": user["id"],
        "display_name": display_name,
        "name_hidden": user["name_hidden"],
        "avatar_id": user.get("avatar_id"),
        "avatar_url": user.get("avatar_url"),
        "points": user["points"],
        "books_completed": user["books_completed"],
        "world_stage": user["world_stage"],
    }


def get_me(user_id: str) -> dict:
    repos = get_repositories()
    return _serialize_full(repos.users.get_by_id(user_id))


def update_me(user_id: str, payload: UpdateProfileRequest) -> dict:
    repos = get_repositories()
    fields = payload.model_dump(exclude_unset=True, mode="json")
    if not fields:
        raise BadRequestError("No fields provided to update")
    user = repos.users.update(user_id, fields)
    return _serialize_full(user)


def upload_avatar(user_id: str, content: bytes, content_type: str) -> dict:
    if not content:
        raise BadRequestError("No file provided")
    repos = get_repositories()
    previous = repos.users.get_by_id(user_id)
    path, url = storage_service.upload_avatar(user_id, content, content_type)
    repos.users.update(user_id, {"avatar_id": path, "avatar_url": url})
    if previous and previous.get("avatar_url") and previous.get("avatar_id"):
        storage_service.delete_avatar(previous["avatar_id"])
    return {"avatar_id": path, "avatar_url": url}


def get_public_profile(user_id: str) -> dict:
    repos = get_repositories()
    user = repos.users.get_by_id(user_id)
    if not user:
        raise NotFoundError("User not found")
    return _serialize_public(user)
