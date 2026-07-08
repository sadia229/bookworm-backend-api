"""Scheduled notification jobs, triggered by Vercel Cron (see vercel.json).

Each job persists a notification row per targeted user (via notification_service)
and sends the matching FCM push, so `GET /notifications` is the full history.
"""

from datetime import UTC, datetime, timedelta

from app.db.container import get_repositories
from app.services import notification_service

# A reader is "inactive" (forest looks poor) after this many days with no session.
_INACTIVE_DAYS = 7


def send_birthday_wishes() -> dict:
    """Notify every user whose date of birth falls on today (server-UTC date)."""
    repos = get_repositories()
    today = datetime.now(UTC).date()
    user_ids = repos.users.list_ids_with_birthday(today.month, today.day)

    notified = 0
    for uid in user_ids:
        user = repos.users.get_by_id(uid)
        name = (user or {}).get("display_name") or "reader"
        notification_service.notify_and_push(
            uid,
            title="Happy Birthday! 🎂",
            body=f"Wishing you a wonderful year of reading, {name}!",
            data={"type": "birthday"},
        )
        notified += 1
    return {"job": "birthday_wishes", "notified": notified}


def send_forest_nudges() -> dict:
    """Nudge readers whose forest looks poor: no reading session in 7+ days.

    Scoped to accounts older than the window so brand-new users aren't nagged
    before they've had a chance to start.
    """
    repos = get_repositories()
    cutoff = (datetime.now(UTC) - timedelta(days=_INACTIVE_DAYS)).isoformat()

    eligible = set(repos.users.list_ids_created_before(cutoff))
    active = repos.sessions.user_ids_active_since(cutoff)
    inactive = sorted(eligible - active)

    notified = notification_service.notify_users(
        inactive,
        title="Your forest misses you 🌱",
        body="It's been a while — read a few pages to bring your forest back to life.",
        data={"type": "forest_nudge"},
    )
    return {"job": "forest_nudge", "notified": notified}
