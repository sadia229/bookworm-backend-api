"""In-memory fakes matching the repository Protocols, used by the test suite.

Mirrors the same business rules the Supabase SQL layer enforces (world-stage
thresholds, finish/log-progress atomicity, ownership checks) so tests exercise
real behavior without needing a live database.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError

_THRESHOLDS = [(100, 5), (50, 4), (30, 3), (15, 2), (5, 1), (0, 0)]

# Starter admin-curated content (mirrors the seed rows in supabase/schema.sql).
_SEED_QUOTES = [
    {"id": "q_001", "text": "A reader lives a thousand lives before he dies.",
     "author": "George R.R. Martin", "category": "Motivation", "sort_order": 1},
    {"id": "q_002", "text": "We loved with a love that was more than love.",
     "author": "Edgar Allan Poe", "category": "Romance", "sort_order": 2},
    {"id": "q_003", "text": "The universe is under no obligation to make sense to you.",
     "author": "Neil deGrasse Tyson", "category": "Sci-Fi", "sort_order": 3},
    {"id": "q_004", "text": "Today a reader, tomorrow a leader.",
     "author": "Margaret Fuller", "category": "Motivation", "sort_order": 4},
]
_SEED_SUMMARIES = [
    {"id": "s_001", "title": "Atomic Habits", "author": "James Clear", "cover": "⚛️",
     "description": "A practical framework for improving every day through tiny 1% changes.",
     "contributor": "Editor"},
    {"id": "s_002", "title": "Deep Work", "author": "Cal Newport", "cover": "🧠",
     "description": "Rules for focused success in a distracted world.",
     "contributor": "Editor"},
]


def world_stage_for(books_completed: int) -> int:
    for threshold, stage in _THRESHOLDS:
        if books_completed >= threshold:
            return stage
    return 0


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class MemoryStore:
    users: dict[str, dict[str, Any]] = field(default_factory=dict)
    books: dict[str, dict[str, Any]] = field(default_factory=dict)
    sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    bookmarks: dict[str, dict[str, Any]] = field(default_factory=dict)
    device_tokens: dict[str, dict[str, Any]] = field(default_factory=dict)
    notifications: dict[str, dict[str, Any]] = field(default_factory=dict)
    refresh_tokens: dict[str, dict[str, Any]] = field(default_factory=dict)
    password_reset_tokens: dict[str, dict[str, Any]] = field(default_factory=dict)
    webhook_events: set[str] = field(default_factory=set)
    quotes: list[dict[str, Any]] = field(default_factory=lambda: list(_SEED_QUOTES))
    summaries: list[dict[str, Any]] = field(default_factory=lambda: list(_SEED_SUMMARIES))


class MemoryUserRepository:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        user_id = fields.get("id") or _new_id()
        now = _now()
        row = {
            "id": user_id,
            "email": fields["email"].lower(),
            "password_hash": fields["password_hash"],
            "display_name": fields["display_name"],
            "name_hidden": fields.get("name_hidden", False),
            "phone": fields.get("phone"),
            "avatar_id": fields.get("avatar_id"),
            "avatar_url": fields.get("avatar_url"),
            "gender": fields.get("gender"),
            "dob": fields.get("dob"),
            "reading_preferences": fields.get("reading_preferences", []),
            "points": 0,
            "books_completed": 0,
            "world_stage": 0,
            "is_premium": fields.get("is_premium", False),
            "premium_until": fields.get("premium_until"),
            "daily_goal_pages": fields.get("daily_goal_pages", 10),
            "yearly_goal_books": fields.get("yearly_goal_books", 12),
            "reminder_time": fields.get("reminder_time", "20:00"),
            "created_at": now,
            "updated_at": now,
        }
        self.store.users[user_id] = row
        return dict(row)

    def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        row = self.store.users.get(user_id)
        return dict(row) if row else None

    def get_many_by_ids(self, user_ids: list[str]) -> dict[str, dict[str, Any]]:
        return {uid: dict(self.store.users[uid]) for uid in user_ids if uid in self.store.users}

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        for row in self.store.users.values():
            if row["email"] == email.lower():
                return dict(row)
        return None

    def update(self, user_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        row = self.store.users.get(user_id)
        if not row:
            return None
        row.update(fields)
        row["updated_at"] = _now()
        return dict(row)

    def _weekly_books(self, user_id: str) -> int:
        cutoff = _now().timestamp() - 7 * 86400
        count = 0
        for book in self.store.books.values():
            if (
                book["user_id"] == user_id
                and book["status"] == "already_read"
                and book.get("finished_at")
                and book["finished_at"].timestamp() >= cutoff
            ):
                count += 1
        return count

    def _leaderboard_rows(self) -> list[dict[str, Any]]:
        rows = []
        for row in self.store.users.values():
            rows.append(
                {
                    "user_id": row["id"],
                    "display_name": row["display_name"],
                    "name_hidden": row["name_hidden"],
                    "avatar_id": row["avatar_id"],
                    "avatar_url": row["avatar_url"],
                    "books_completed": row["books_completed"],
                    "points": row["points"],
                    "world_stage": row["world_stage"],
                    "updated_at": row["updated_at"],
                    "weekly_books": self._weekly_books(row["id"]),
                }
            )
        return rows

    def list_leaderboard(
        self, period: str, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int]:
        rows = self._leaderboard_rows()
        metric = "weekly_books" if period == "weekly" else "books_completed"
        rows.sort(key=lambda r: (-r[metric], -r["points"], -r["updated_at"].timestamp()))
        total = len(rows)
        return rows[offset : offset + limit], total

    def get_rank(self, user_id: str, period: str) -> dict[str, Any] | None:
        rows = self._leaderboard_rows()
        metric = "weekly_books" if period == "weekly" else "books_completed"
        rows.sort(key=lambda r: (-r[metric], -r["points"], -r["updated_at"].timestamp()))
        for index, row in enumerate(rows):
            if row["user_id"] == user_id:
                return {
                    "rank": index + 1,
                    "user_id": user_id,
                    "books_completed": row["books_completed"],
                    "points": row["points"],
                }
        return None


class MemoryBookRepository:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        book_id = fields.get("id") or _new_id()
        now = _now()
        row = {
            "id": book_id,
            "user_id": fields["user_id"],
            "title": fields["title"],
            "author": fields["author"],
            "genre": fields.get("genre"),
            "cover_url": fields.get("cover_url"),
            "total_pages": fields.get("total_pages"),
            "current_page": fields.get("current_page", 0),
            "status": fields.get("status", "currently_reading"),
            "started_at": fields.get("started_at") or now,
            "finished_at": fields.get("finished_at"),
            "rating": fields.get("rating"),
            "summary": fields.get("summary"),
            "created_at": now,
            "updated_at": now,
        }
        self.store.books[book_id] = row
        return dict(row)

    def get_by_id(self, book_id: str) -> dict[str, Any] | None:
        row = self.store.books.get(book_id)
        return dict(row) if row else None

    def get_many_by_ids(self, book_ids: list[str]) -> dict[str, dict[str, Any]]:
        return {bid: dict(self.store.books[bid]) for bid in book_ids if bid in self.store.books}

    def _matches(self, row, status, q, genre) -> bool:
        if status and row["status"] != status:
            return False
        if genre and row["genre"] != genre:
            return False
        if q:
            needle = q.lower()
            if needle not in row["title"].lower() and needle not in row["author"].lower():
                return False
        return True

    def _sort_key(self, sort: str):
        reverse_map = {
            "title": ("title", False),
            "-title": ("title", True),
            "-created_at": ("created_at", True),
            "-finished_at": ("finished_at", True),
            "-updated_at": ("updated_at", True),
            "-rating": ("rating", True),
        }
        column, desc = reverse_map.get(sort, ("updated_at", True))

        def key(row):
            value = row.get(column)
            if value is None:
                return (0,) if not isinstance(value, str) else ""
            if isinstance(value, datetime):
                return value.timestamp()
            return value

        return key, desc

    def list_by_user(
        self,
        user_id: str,
        status: str | None,
        q: str | None,
        genre: str | None,
        sort: str,
        page: int,
        size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [
            r
            for r in self.store.books.values()
            if r["user_id"] == user_id and self._matches(r, status, q, genre)
        ]
        key, desc = self._sort_key(sort)
        rows.sort(key=key, reverse=desc)
        total = len(rows)
        offset = (page - 1) * size
        return [dict(r) for r in rows[offset : offset + size]], total

    def list_public_finished(
        self, user_id: str, sort: str, page: int, size: int
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [
            r
            for r in self.store.books.values()
            if r["user_id"] == user_id and r["status"] == "already_read"
        ]
        key, desc = self._sort_key(sort if sort != "-updated_at" else "-finished_at")
        rows.sort(key=key, reverse=desc)
        total = len(rows)
        offset = (page - 1) * size
        return [dict(r) for r in rows[offset : offset + size]], total

    def update(self, book_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        row = self.store.books.get(book_id)
        if not row:
            return None
        row.update(fields)
        row["updated_at"] = _now()
        return dict(row)

    def delete(self, book_id: str) -> bool:
        return self.store.books.pop(book_id, None) is not None

    def finish(
        self,
        book_id: str,
        user_id: str,
        summary: str,
        rating: int | None,
        finished_at: str | None,
    ) -> dict[str, Any]:
        book = self.store.books.get(book_id)
        if not book:
            raise NotFoundError("Book not found")
        if book["user_id"] != user_id:
            raise ForbiddenError("You do not have access to this book")
        if book["status"] == "already_read":
            raise ConflictError("This book is already marked as read")

        finished_dt = finished_at if isinstance(finished_at, datetime) else _now()
        book["status"] = "already_read"
        book["finished_at"] = finished_dt
        book["rating"] = rating
        book["summary"] = summary
        if book.get("total_pages"):
            book["current_page"] = book["total_pages"]
        book["updated_at"] = _now()

        user = self.store.users[user_id]
        previous_stage = user["world_stage"]
        user["points"] += 10
        user["books_completed"] += 1
        new_stage = world_stage_for(user["books_completed"])
        user["world_stage"] = new_stage
        user["updated_at"] = _now()

        return {
            "book": {
                "id": book["id"],
                "title": book["title"],
                "status": book["status"],
                "finished_at": book["finished_at"],
                "rating": book["rating"],
                "summary": book["summary"],
                "current_page": book["current_page"],
                "total_pages": book["total_pages"],
            },
            "progression": {
                "books_completed": user["books_completed"],
                "points_awarded": 10,
                "points_total": user["points"],
                "previous_world_stage": previous_stage,
                "world_stage": new_stage,
                "stage_changed": new_stage != previous_stage,
            },
        }


class MemoryReadingSessionRepository:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def log(
        self,
        book_id: str,
        user_id: str,
        pages_read: int,
        minutes: int | None,
        date: str | None,
    ) -> dict[str, Any]:
        book = self.store.books.get(book_id)
        if not book:
            raise NotFoundError("Book not found")
        if book["user_id"] != user_id:
            raise ForbiddenError("You do not have access to this book")
        if book["status"] == "already_read":
            raise ConflictError("This book is already finished")

        new_page = book["current_page"] + pages_read
        if book.get("total_pages") and new_page > book["total_pages"]:
            new_page = book["total_pages"]
        book["current_page"] = new_page
        book["updated_at"] = _now()

        session_id = _new_id()
        session_date = date if isinstance(date, datetime) else _now()
        session = {
            "id": session_id,
            "book_id": book_id,
            "user_id": user_id,
            "pages_read": pages_read,
            "minutes": minutes,
            "date": session_date,
            "created_at": _now(),
        }
        self.store.sessions[session_id] = session

        return {
            "session": {
                "id": session_id,
                "book_id": book_id,
                "pages_read": pages_read,
                "minutes": minutes,
                "date": session_date,
            },
            "book": {
                "id": book["id"],
                "current_page": new_page,
                "total_pages": book["total_pages"],
                "status": book["status"],
            },
        }

    def list_by_book(
        self, book_id: str, page: int, size: int
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [r for r in self.store.sessions.values() if r["book_id"] == book_id]
        rows.sort(key=lambda r: r["date"], reverse=True)
        total = len(rows)
        offset = (page - 1) * size
        return [dict(r) for r in rows[offset : offset + size]], total

    def list_by_user_window(
        self, user_id: str, date_from: str, date_to: str
    ) -> list[dict[str, Any]]:
        rows = [
            dict(r)
            for r in self.store.sessions.values()
            if r["user_id"] == user_id and date_from <= r["date"] <= date_to
        ]
        rows.sort(key=lambda r: r["date"])
        return rows

    def list_all_by_user(self, user_id: str) -> list[dict[str, Any]]:
        rows = [dict(r) for r in self.store.sessions.values() if r["user_id"] == user_id]
        rows.sort(key=lambda r: r["date"])
        return rows


class MemoryBookmarkRepository:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def create(self, user_id: str, book_id: str) -> dict[str, Any]:
        bookmark_id = _new_id()
        row = {"id": bookmark_id, "user_id": user_id, "book_id": book_id, "created_at": _now()}
        self.store.bookmarks[bookmark_id] = row
        return dict(row)

    def get_by_id(self, bookmark_id: str) -> dict[str, Any] | None:
        row = self.store.bookmarks.get(bookmark_id)
        return dict(row) if row else None

    def exists(self, user_id: str, book_id: str) -> bool:
        return any(
            r["user_id"] == user_id and r["book_id"] == book_id
            for r in self.store.bookmarks.values()
        )

    def list_by_user(
        self, user_id: str, page: int, size: int
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [r for r in self.store.bookmarks.values() if r["user_id"] == user_id]
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        total = len(rows)
        offset = (page - 1) * size
        return [dict(r) for r in rows[offset : offset + size]], total

    def bookmarked_book_ids(self, user_id: str, book_ids: list[str]) -> set[str]:
        return {
            r["book_id"]
            for r in self.store.bookmarks.values()
            if r["user_id"] == user_id and r["book_id"] in book_ids
        }

    def delete(self, bookmark_id: str) -> bool:
        return self.store.bookmarks.pop(bookmark_id, None) is not None

    def delete_by_book(self, user_id: str, book_id: str) -> bool:
        match = next(
            (
                bid
                for bid, r in self.store.bookmarks.items()
                if r["user_id"] == user_id and r["book_id"] == book_id
            ),
            None,
        )
        if match:
            del self.store.bookmarks[match]
            return True
        return False


class MemoryDeviceTokenRepository:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def upsert(self, user_id: str, token: str, platform: str | None) -> dict[str, Any]:
        existing = self.store.device_tokens.get(token)
        now = _now()
        row = {
            "id": existing["id"] if existing else _new_id(),
            "user_id": user_id,
            "token": token,
            "platform": platform,
            "created_at": existing["created_at"] if existing else now,
            "updated_at": now,
        }
        self.store.device_tokens[token] = row
        return dict(row)

    def delete(self, token: str) -> None:
        self.store.device_tokens.pop(token, None)

    def list_tokens_for_user(self, user_id: str) -> list[str]:
        return [t for t, r in self.store.device_tokens.items() if r["user_id"] == user_id]


class MemoryNotificationRepository:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def create(
        self, user_id: str, title: str, body: str, image_url: str | None, data: dict
    ) -> dict[str, Any]:
        notification_id = _new_id()
        row = {
            "id": notification_id,
            "user_id": user_id,
            "title": title,
            "body": body,
            "image_url": image_url,
            "data": data,
            "is_read": False,
            "received_at": _now(),
        }
        self.store.notifications[notification_id] = row
        return dict(row)

    def get_by_id(self, notification_id: str) -> dict[str, Any] | None:
        row = self.store.notifications.get(notification_id)
        return dict(row) if row else None

    def list_by_user(
        self, user_id: str, unread_only: bool, page: int, size: int
    ) -> tuple[list[dict[str, Any]], int, int]:
        rows = [r for r in self.store.notifications.values() if r["user_id"] == user_id]
        if unread_only:
            rows = [r for r in rows if not r["is_read"]]
        rows.sort(key=lambda r: r["received_at"], reverse=True)
        total = len(rows)
        offset = (page - 1) * size
        return (
            [dict(r) for r in rows[offset : offset + size]],
            total,
            self.unread_count(user_id),
        )

    def mark_read(self, notification_id: str) -> dict[str, Any]:
        row = self.store.notifications[notification_id]
        row["is_read"] = True
        return dict(row)

    def mark_all_read(self, user_id: str) -> int:
        count = 0
        for row in self.store.notifications.values():
            if row["user_id"] == user_id and not row["is_read"]:
                row["is_read"] = True
                count += 1
        return count

    def delete(self, notification_id: str) -> bool:
        return self.store.notifications.pop(notification_id, None) is not None

    def unread_count(self, user_id: str) -> int:
        return sum(
            1
            for r in self.store.notifications.values()
            if r["user_id"] == user_id and not r["is_read"]
        )


class MemoryRefreshTokenRepository:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def create(self, jti: str, user_id: str, family_id: str, expires_at: str) -> None:
        self.store.refresh_tokens[jti] = {
            "id": jti,
            "user_id": user_id,
            "family_id": family_id,
            "revoked": False,
            "expires_at": expires_at,
            "created_at": _now(),
        }

    def get(self, jti: str) -> dict[str, Any] | None:
        row = self.store.refresh_tokens.get(jti)
        return dict(row) if row else None

    def revoke(self, jti: str) -> None:
        if jti in self.store.refresh_tokens:
            self.store.refresh_tokens[jti]["revoked"] = True

    def revoke_family(self, family_id: str) -> None:
        for row in self.store.refresh_tokens.values():
            if row["family_id"] == family_id:
                row["revoked"] = True

    def revoke_all_for_user(self, user_id: str) -> None:
        for row in self.store.refresh_tokens.values():
            if row["user_id"] == user_id:
                row["revoked"] = True


class MemoryPasswordResetRepository:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def create(self, user_id: str, token_hash: str, expires_at: str) -> dict[str, Any]:
        reset_id = _new_id()
        row = {
            "id": reset_id,
            "user_id": user_id,
            "token_hash": token_hash,
            "used": False,
            "expires_at": expires_at,
            "created_at": _now(),
        }
        self.store.password_reset_tokens[reset_id] = row
        return dict(row)

    def get_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        for row in self.store.password_reset_tokens.values():
            if row["token_hash"] == token_hash:
                return dict(row)
        return None

    def mark_used(self, reset_id: str) -> None:
        if reset_id in self.store.password_reset_tokens:
            self.store.password_reset_tokens[reset_id]["used"] = True


class MemoryWebhookEventRepository:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def was_processed(self, event_id: str) -> bool:
        return event_id in self.store.webhook_events

    def mark_processed(self, event_id: str) -> None:
        self.store.webhook_events.add(event_id)


class MemoryContentRepository:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def list_quotes(self, category: str | None, limit: int) -> list[dict[str, Any]]:
        rows = [dict(q) for q in self.store.quotes if category is None or q["category"] == category]
        rows.sort(key=lambda q: q.get("sort_order", 0))
        return rows[:limit]

    def list_summaries(self, page: int, size: int) -> tuple[list[dict[str, Any]], int]:
        rows = [dict(s) for s in self.store.summaries]
        total = len(rows)
        offset = (page - 1) * size
        return rows[offset : offset + size], total
