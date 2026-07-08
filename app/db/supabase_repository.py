"""Supabase (PostgREST + RPC) implementations of the repository interfaces."""

from typing import Any

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.supabase_client import get_supabase

_SORT_MAP = {
    "title": ("title", False),
    "-title": ("title", True),
    "-created_at": ("created_at", True),
    "-finished_at": ("finished_at", True),
    "-updated_at": ("updated_at", True),
    "-rating": ("rating", True),
}


def _sort_tuple(sort: str, default: str = "-updated_at") -> tuple[str, bool]:
    return _SORT_MAP.get(sort, _SORT_MAP[default])


def _rpc_error_to_app_error(message: str) -> Exception:
    if "BOOK_NOT_FOUND" in message:
        return NotFoundError("Book not found")
    if "BOOK_FORBIDDEN" in message:
        return ForbiddenError("You do not have access to this book")
    if "BOOK_ALREADY_FINISHED" in message:
        return ConflictError("This book is already marked as read")
    return Exception(message)


class SupabaseUserRepository:
    def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        res = get_supabase().table("users").insert(fields).execute()
        return res.data[0]

    def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        res = get_supabase().table("users").select("*").eq("id", user_id).execute()
        return res.data[0] if res.data else None

    def get_many_by_ids(self, user_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not user_ids:
            return {}
        res = get_supabase().table("users").select("*").in_("id", user_ids).execute()
        return {row["id"]: row for row in res.data}

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        res = get_supabase().table("users").select("*").eq("email", email.lower()).execute()
        return res.data[0] if res.data else None

    def update(self, user_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        res = get_supabase().table("users").update(fields).eq("id", user_id).execute()
        return res.data[0] if res.data else None

    def list_leaderboard(
        self, period: str, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int]:
        client = get_supabase()
        query = client.table("leaderboard_view").select("*", count="exact")
        if period == "weekly":
            query = query.order("weekly_books", desc=True).order("points", desc=True)
        else:
            query = query.order("books_completed", desc=True).order("points", desc=True)
        query = query.order("updated_at", desc=True).range(offset, offset + limit - 1)
        res = query.execute()
        return res.data, res.count or 0

    def get_rank(self, user_id: str, period: str) -> dict[str, Any] | None:
        client = get_supabase()
        me_res = (
            client.table("leaderboard_view").select("*").eq("user_id", user_id).execute()
        )
        if not me_res.data:
            return None
        me = me_res.data[0]
        metric = "weekly_books" if period == "weekly" else "books_completed"
        my_metric = me[metric]
        my_points = me["points"]

        better = (
            client.table("leaderboard_view")
            .select("user_id", count="exact")
            .gt(metric, my_metric)
            .execute()
        )
        tied_better_points = (
            client.table("leaderboard_view")
            .select("user_id", count="exact")
            .eq(metric, my_metric)
            .gt("points", my_points)
            .execute()
        )
        rank = (better.count or 0) + (tied_better_points.count or 0) + 1
        return {
            "rank": rank,
            "user_id": user_id,
            "books_completed": me["books_completed"],
            "points": me["points"],
        }


class SupabaseBookRepository:
    def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        res = get_supabase().table("books").insert(fields).execute()
        return res.data[0]

    def get_by_id(self, book_id: str) -> dict[str, Any] | None:
        res = get_supabase().table("books").select("*").eq("id", book_id).execute()
        return res.data[0] if res.data else None

    def get_many_by_ids(self, book_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not book_ids:
            return {}
        res = get_supabase().table("books").select("*").in_("id", book_ids).execute()
        return {row["id"]: row for row in res.data}

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
        client = get_supabase()
        query = client.table("books").select("*", count="exact").eq("user_id", user_id)
        if status:
            query = query.eq("status", status)
        if genre:
            query = query.eq("genre", genre)
        if q:
            escaped = q.replace(",", "").replace("%", "")
            query = query.or_(f"title.ilike.%{escaped}%,author.ilike.%{escaped}%")
        column, desc = _sort_tuple(sort)
        offset = (page - 1) * size
        res = query.order(column, desc=desc).range(offset, offset + size - 1).execute()
        return res.data, res.count or 0

    def list_public_finished(
        self, user_id: str, sort: str, page: int, size: int
    ) -> tuple[list[dict[str, Any]], int]:
        client = get_supabase()
        query = (
            client.table("books")
            .select("*", count="exact")
            .eq("user_id", user_id)
            .eq("status", "already_read")
        )
        column, desc = _sort_tuple(sort, default="-finished_at")
        offset = (page - 1) * size
        res = query.order(column, desc=desc).range(offset, offset + size - 1).execute()
        return res.data, res.count or 0

    def update(self, book_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        res = get_supabase().table("books").update(fields).eq("id", book_id).execute()
        return res.data[0] if res.data else None

    def delete(self, book_id: str) -> bool:
        res = get_supabase().table("books").delete().eq("id", book_id).execute()
        return bool(res.data)

    def finish(
        self,
        book_id: str,
        user_id: str,
        summary: str,
        rating: int | None,
        finished_at: str | None,
    ) -> dict[str, Any]:
        client = get_supabase()
        try:
            res = client.rpc(
                "fn_finish_book",
                {
                    "p_book_id": book_id,
                    "p_user_id": user_id,
                    "p_summary": summary,
                    "p_rating": rating,
                    "p_finished_at": finished_at,
                },
            ).execute()
        except Exception as exc:  # noqa: BLE001 - translate DB signal to AppError
            raise _rpc_error_to_app_error(str(exc)) from exc
        return res.data


class SupabaseReadingSessionRepository:
    def log(
        self,
        book_id: str,
        user_id: str,
        pages_read: int,
        minutes: int | None,
        date: str | None,
    ) -> dict[str, Any]:
        client = get_supabase()
        try:
            res = client.rpc(
                "fn_log_progress",
                {
                    "p_book_id": book_id,
                    "p_user_id": user_id,
                    "p_pages_read": pages_read,
                    "p_minutes": minutes,
                    "p_date": date,
                },
            ).execute()
        except Exception as exc:  # noqa: BLE001
            raise _rpc_error_to_app_error(str(exc)) from exc
        return res.data

    def list_by_book(
        self, book_id: str, page: int, size: int
    ) -> tuple[list[dict[str, Any]], int]:
        client = get_supabase()
        offset = (page - 1) * size
        res = (
            client.table("reading_sessions")
            .select("*", count="exact")
            .eq("book_id", book_id)
            .order("date", desc=True)
            .range(offset, offset + size - 1)
            .execute()
        )
        return res.data, res.count or 0

    def list_by_user_window(
        self, user_id: str, date_from: str, date_to: str
    ) -> list[dict[str, Any]]:
        res = (
            get_supabase()
            .table("reading_sessions")
            .select("*")
            .eq("user_id", user_id)
            .gte("date", date_from)
            .lte("date", date_to)
            .order("date")
            .execute()
        )
        return res.data

    def list_all_by_user(self, user_id: str) -> list[dict[str, Any]]:
        res = (
            get_supabase()
            .table("reading_sessions")
            .select("*")
            .eq("user_id", user_id)
            .order("date")
            .execute()
        )
        return res.data


class SupabaseBookmarkRepository:
    def create(self, user_id: str, book_id: str) -> dict[str, Any]:
        res = (
            get_supabase()
            .table("bookmarks")
            .insert({"user_id": user_id, "book_id": book_id})
            .execute()
        )
        return res.data[0]

    def get_by_id(self, bookmark_id: str) -> dict[str, Any] | None:
        res = get_supabase().table("bookmarks").select("*").eq("id", bookmark_id).execute()
        return res.data[0] if res.data else None

    def exists(self, user_id: str, book_id: str) -> bool:
        res = (
            get_supabase()
            .table("bookmarks")
            .select("id")
            .eq("user_id", user_id)
            .eq("book_id", book_id)
            .execute()
        )
        return bool(res.data)

    def list_by_user(
        self, user_id: str, page: int, size: int
    ) -> tuple[list[dict[str, Any]], int]:
        offset = (page - 1) * size
        res = (
            get_supabase()
            .table("bookmarks")
            .select("*", count="exact")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + size - 1)
            .execute()
        )
        return res.data, res.count or 0

    def bookmarked_book_ids(self, user_id: str, book_ids: list[str]) -> set[str]:
        if not book_ids:
            return set()
        res = (
            get_supabase()
            .table("bookmarks")
            .select("book_id")
            .eq("user_id", user_id)
            .in_("book_id", book_ids)
            .execute()
        )
        return {row["book_id"] for row in res.data}

    def delete(self, bookmark_id: str) -> bool:
        res = get_supabase().table("bookmarks").delete().eq("id", bookmark_id).execute()
        return bool(res.data)

    def delete_by_book(self, user_id: str, book_id: str) -> bool:
        res = (
            get_supabase()
            .table("bookmarks")
            .delete()
            .eq("user_id", user_id)
            .eq("book_id", book_id)
            .execute()
        )
        return bool(res.data)


class SupabaseDeviceTokenRepository:
    def upsert(self, user_id: str, token: str, platform: str | None) -> dict[str, Any]:
        res = (
            get_supabase()
            .table("device_tokens")
            .upsert(
                {"user_id": user_id, "token": token, "platform": platform},
                on_conflict="token",
            )
            .execute()
        )
        return res.data[0]

    def delete(self, token: str) -> None:
        get_supabase().table("device_tokens").delete().eq("token", token).execute()

    def list_tokens_for_user(self, user_id: str) -> list[str]:
        res = (
            get_supabase()
            .table("device_tokens")
            .select("token")
            .eq("user_id", user_id)
            .execute()
        )
        return [row["token"] for row in res.data]


class SupabaseNotificationRepository:
    def create(
        self, user_id: str, title: str, body: str, image_url: str | None, data: dict
    ) -> dict[str, Any]:
        res = (
            get_supabase()
            .table("notifications")
            .insert(
                {
                    "user_id": user_id,
                    "title": title,
                    "body": body,
                    "image_url": image_url,
                    "data": data,
                }
            )
            .execute()
        )
        return res.data[0]

    def get_by_id(self, notification_id: str) -> dict[str, Any] | None:
        res = (
            get_supabase()
            .table("notifications")
            .select("*")
            .eq("id", notification_id)
            .execute()
        )
        return res.data[0] if res.data else None

    def list_by_user(
        self, user_id: str, unread_only: bool, page: int, size: int
    ) -> tuple[list[dict[str, Any]], int, int]:
        client = get_supabase()
        query = client.table("notifications").select("*", count="exact").eq("user_id", user_id)
        if unread_only:
            query = query.eq("is_read", False)
        offset = (page - 1) * size
        res = query.order("received_at", desc=True).range(offset, offset + size - 1).execute()
        return res.data, res.count or 0, self.unread_count(user_id)

    def mark_read(self, notification_id: str) -> dict[str, Any]:
        res = (
            get_supabase()
            .table("notifications")
            .update({"is_read": True})
            .eq("id", notification_id)
            .execute()
        )
        return res.data[0]

    def mark_all_read(self, user_id: str) -> int:
        res = (
            get_supabase()
            .table("notifications")
            .update({"is_read": True})
            .eq("user_id", user_id)
            .eq("is_read", False)
            .execute()
        )
        return len(res.data)

    def delete(self, notification_id: str) -> bool:
        res = (
            get_supabase()
            .table("notifications")
            .delete()
            .eq("id", notification_id)
            .execute()
        )
        return bool(res.data)

    def unread_count(self, user_id: str) -> int:
        res = (
            get_supabase()
            .table("notifications")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("is_read", False)
            .execute()
        )
        return res.count or 0


class SupabaseRefreshTokenRepository:
    def create(self, jti: str, user_id: str, family_id: str, expires_at: str) -> None:
        get_supabase().table("refresh_tokens").insert(
            {
                "id": jti,
                "user_id": user_id,
                "family_id": family_id,
                "expires_at": expires_at,
            }
        ).execute()

    def get(self, jti: str) -> dict[str, Any] | None:
        res = get_supabase().table("refresh_tokens").select("*").eq("id", jti).execute()
        return res.data[0] if res.data else None

    def revoke(self, jti: str) -> None:
        get_supabase().table("refresh_tokens").update({"revoked": True}).eq("id", jti).execute()

    def revoke_family(self, family_id: str) -> None:
        get_supabase().table("refresh_tokens").update({"revoked": True}).eq(
            "family_id", family_id
        ).execute()

    def revoke_all_for_user(self, user_id: str) -> None:
        get_supabase().table("refresh_tokens").update({"revoked": True}).eq(
            "user_id", user_id
        ).execute()


class SupabasePasswordResetRepository:
    def create(self, user_id: str, token_hash: str, expires_at: str) -> dict[str, Any]:
        res = (
            get_supabase()
            .table("password_reset_tokens")
            .insert({"user_id": user_id, "token_hash": token_hash, "expires_at": expires_at})
            .execute()
        )
        return res.data[0]

    def get_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        res = (
            get_supabase()
            .table("password_reset_tokens")
            .select("*")
            .eq("token_hash", token_hash)
            .execute()
        )
        return res.data[0] if res.data else None

    def mark_used(self, reset_id: str) -> None:
        get_supabase().table("password_reset_tokens").update({"used": True}).eq(
            "id", reset_id
        ).execute()


class SupabaseContentRepository:
    def list_quotes(self, category: str | None, limit: int) -> list[dict[str, Any]]:
        query = (
            get_supabase()
            .table("quotes")
            .select("*")
            .eq("is_active", True)
        )
        if category:
            query = query.eq("category", category)
        res = query.order("sort_order").limit(limit).execute()
        return res.data

    def list_summaries(self, page: int, size: int) -> tuple[list[dict[str, Any]], int]:
        offset = (page - 1) * size
        res = (
            get_supabase()
            .table("summaries")
            .select("*", count="exact")
            .eq("is_active", True)
            .order("created_at", desc=True)
            .range(offset, offset + size - 1)
            .execute()
        )
        return res.data, res.count or 0


class SupabaseWebhookEventRepository:
    def was_processed(self, event_id: str) -> bool:
        res = (
            get_supabase()
            .table("processed_webhook_events")
            .select("id")
            .eq("id", event_id)
            .execute()
        )
        return bool(res.data)

    def mark_processed(self, event_id: str) -> None:
        # upsert so a racing redelivery of the same event.id can't 409.
        get_supabase().table("processed_webhook_events").upsert(
            {"id": event_id}, on_conflict="id"
        ).execute()
