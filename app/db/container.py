"""Wires up either the Supabase-backed repositories or the in-memory fakes.

`app.main` uses the Supabase container. Tests override this with
`app.db.container.use_memory()` so the whole app runs against in-process
fakes without a live database.
"""

from dataclasses import dataclass

from app.db import memory_repository as mem
from app.db import supabase_repository as sup


@dataclass
class Repositories:
    users: object
    books: object
    sessions: object
    bookmarks: object
    device_tokens: object
    notifications: object
    refresh_tokens: object
    password_resets: object
    webhook_events: object
    content: object


def build_supabase_repositories() -> Repositories:
    return Repositories(
        users=sup.SupabaseUserRepository(),
        books=sup.SupabaseBookRepository(),
        sessions=sup.SupabaseReadingSessionRepository(),
        bookmarks=sup.SupabaseBookmarkRepository(),
        device_tokens=sup.SupabaseDeviceTokenRepository(),
        notifications=sup.SupabaseNotificationRepository(),
        refresh_tokens=sup.SupabaseRefreshTokenRepository(),
        password_resets=sup.SupabasePasswordResetRepository(),
        webhook_events=sup.SupabaseWebhookEventRepository(),
        content=sup.SupabaseContentRepository(),
    )


def build_memory_repositories() -> Repositories:
    store = mem.MemoryStore()
    return Repositories(
        users=mem.MemoryUserRepository(store),
        books=mem.MemoryBookRepository(store),
        sessions=mem.MemoryReadingSessionRepository(store),
        bookmarks=mem.MemoryBookmarkRepository(store),
        device_tokens=mem.MemoryDeviceTokenRepository(store),
        notifications=mem.MemoryNotificationRepository(store),
        refresh_tokens=mem.MemoryRefreshTokenRepository(store),
        password_resets=mem.MemoryPasswordResetRepository(store),
        webhook_events=mem.MemoryWebhookEventRepository(store),
        content=mem.MemoryContentRepository(store),
    )


_repos: Repositories | None = None


def get_repositories() -> Repositories:
    global _repos
    if _repos is None:
        _repos = build_supabase_repositories()
    return _repos


def set_repositories(repos: Repositories) -> None:
    global _repos
    _repos = repos


def use_memory() -> Repositories:
    repos = build_memory_repositories()
    set_repositories(repos)
    return repos
