from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.timeutils import iso
from app.db.container import get_repositories
from app.services import push_service


def register_device_token(user_id: str, token: str, platform: str | None) -> dict:
    repos = get_repositories()
    repos.device_tokens.upsert(user_id, token, platform)
    return {"token_registered": True, "platform": platform}


def remove_device_token(user_id: str, token: str) -> None:
    repos = get_repositories()
    repos.device_tokens.delete(token)


def list_notifications(
    user_id: str, unread_only: bool, page: int, size: int
) -> tuple[list[dict], int, int]:
    repos = get_repositories()
    items, total, unread_count = repos.notifications.list_by_user(
        user_id, unread_only, page, size
    )
    serialized = [
        {
            "id": n["id"],
            "title": n["title"],
            "body": n["body"],
            "image_url": n.get("image_url"),
            "data": n.get("data") or {},
            "is_read": n["is_read"],
            "received_at": iso(n["received_at"]),
        }
        for n in items
    ]
    return serialized, total, unread_count


def mark_read(user_id: str, notification_id: str) -> dict:
    repos = get_repositories()
    notification = repos.notifications.get_by_id(notification_id)
    if not notification:
        raise NotFoundError("Notification not found")
    if notification["user_id"] != user_id:
        raise ForbiddenError("You do not have access to this notification")
    updated = repos.notifications.mark_read(notification_id)
    return {
        "id": updated["id"],
        "is_read": updated["is_read"],
        "unread_count": repos.notifications.unread_count(user_id),
    }


def mark_all_read(user_id: str) -> dict:
    repos = get_repositories()
    marked = repos.notifications.mark_all_read(user_id)
    return {"marked_read": marked, "unread_count": repos.notifications.unread_count(user_id)}


def delete_notification(user_id: str, notification_id: str) -> None:
    repos = get_repositories()
    notification = repos.notifications.get_by_id(notification_id)
    if not notification:
        raise NotFoundError("Notification not found")
    if notification["user_id"] != user_id:
        raise ForbiddenError("You do not have access to this notification")
    repos.notifications.delete(notification_id)


def notify_and_push(
    user_id: str, title: str, body: str, data: dict | None = None, image_url: str | None = None
) -> None:
    """Persist a notification row in Supabase and attempt an FCM push.

    This is the "store push notifications in Supabase + endpoint" integration:
    history is always recorded even if Firebase isn't configured or delivery
    fails, so `GET /notifications` stays a source of truth for the client.
    """
    repos = get_repositories()
    repos.notifications.create(user_id, title, body, image_url, data or {})
    tokens = repos.device_tokens.list_tokens_for_user(user_id)
    push_service.send_push(tokens, title, body, data)


def notify_users(
    user_ids: list[str],
    title: str,
    body: str,
    data: dict | None = None,
    image_url: str | None = None,
) -> int:
    """Fan out one notification to many users: persist a row per user, then push.

    Returns the number of users notified. Used by the admin summary broadcast and
    the scheduled birthday / forest-nudge jobs so every delivered push also has a
    saved history row.
    """
    if not user_ids:
        return 0
    repos = get_repositories()
    count = repos.notifications.create_bulk(user_ids, title, body, image_url, data or {})
    tokens = repos.device_tokens.list_tokens_for_users(user_ids)
    push_service.send_push(tokens, title, body, data)
    return count
