from datetime import UTC, date, datetime, timedelta

from app.core.exceptions import ValidationAppError
from app.core.timeutils import iso, parse_dt
from app.db.container import get_repositories
from app.models.progress import LogProgressRequest


def log_progress(user_id: str, book_id: str, payload: LogProgressRequest) -> dict:
    repos = get_repositories()
    fields = payload.model_dump(mode="json")
    result = repos.sessions.log(
        book_id, user_id, fields["pages_read"], fields.get("minutes"), fields.get("date")
    )
    session = result["session"]
    book = result["book"]
    total = book.get("total_pages")
    progress = round(book["current_page"] / total, 4) if total else 0.0

    return {
        "session": {
            "id": session["id"],
            "book_id": session["book_id"],
            "pages_read": session["pages_read"],
            "minutes": session.get("minutes"),
            "date": iso(session["date"]),
        },
        "book": {
            "id": book["id"],
            "current_page": book["current_page"],
            "total_pages": book.get("total_pages"),
            "progress": progress,
            "status": book["status"],
        },
    }


def book_progress_history(
    user_id: str, book_id: str, page: int, size: int
) -> tuple[list[dict], int]:
    from app.services.book_service import get_owned_book  # local import avoids a cycle

    repos = get_repositories()
    get_owned_book(repos, user_id, book_id)
    items, total = repos.sessions.list_by_book(book_id, page, size)
    serialized = [
        {
            "id": s["id"],
            "pages_read": s["pages_read"],
            "minutes": s.get("minutes"),
            "date": iso(s["date"]),
        }
        for s in items
    ]
    return serialized, total


def _bucket_label(d: date, group_by: str) -> str:
    if group_by == "week":
        start = d - timedelta(days=d.weekday())
        return start.isoformat()
    if group_by == "month":
        return d.strftime("%Y-%m")
    return d.isoformat()


def _iter_bucket_starts(d_from: date, d_to: date, group_by: str) -> list[date]:
    starts: list[date] = []
    if group_by == "day":
        cursor = d_from
        while cursor <= d_to:
            starts.append(cursor)
            cursor += timedelta(days=1)
    elif group_by == "week":
        cursor = d_from - timedelta(days=d_from.weekday())
        while cursor <= d_to:
            starts.append(cursor)
            cursor += timedelta(days=7)
    else:
        cursor = d_from.replace(day=1)
        while cursor <= d_to:
            starts.append(cursor)
            year = cursor.year + (cursor.month // 12)
            month = cursor.month % 12 + 1
            cursor = cursor.replace(year=year, month=month)
    return starts


def activity_window(
    user_id: str, date_from: date | None, date_to: date | None, group_by: str
) -> dict:
    repos = get_repositories()
    today = datetime.now(UTC).date()
    d_to = date_to or today
    d_from = date_from or (d_to - timedelta(days=6))

    if d_from > d_to or (d_to - d_from).days > 366:
        raise ValidationAppError(
            "'from' must be on or before 'to'", {"errors": {"from": "invalid_range"}}
        )

    sessions = repos.sessions.list_by_user_window(
        user_id,
        f"{d_from.isoformat()}T00:00:00+00:00",
        f"{d_to.isoformat()}T23:59:59.999999+00:00",
    )

    bucket_starts = _iter_bucket_starts(d_from, d_to, group_by)
    order = [_bucket_label(b, group_by) for b in bucket_starts]
    buckets = {
        label: {"label": label, "date": label, "pages": 0, "minutes": 0, "sessions": 0}
        for label in order
    }

    total_pages = 0
    for session in sessions:
        session_date = parse_dt(session["date"]).date()
        label = _bucket_label(session_date, group_by)
        if label not in buckets:
            continue
        buckets[label]["pages"] += session["pages_read"]
        buckets[label]["minutes"] += session.get("minutes") or 0
        buckets[label]["sessions"] += 1
        total_pages += session["pages_read"]

    return {
        "from": d_from.isoformat(),
        "to": d_to.isoformat(),
        "group_by": group_by,
        "total_pages": total_pages,
        "buckets": [buckets[label] for label in order],
    }
