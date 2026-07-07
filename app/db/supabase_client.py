from functools import lru_cache

from app.config import get_settings
from supabase import Client, create_client

AVATAR_BUCKET = "avatars"
COVER_BUCKET = "book-covers"


@lru_cache
def get_supabase() -> Client:
    """Server-side client authenticated with the service_role key.

    This bypasses Row Level Security, so all authorization (ownership,
    premium gating, etc.) is enforced in the service layer, not by RLS.
    """
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def ensure_storage_buckets() -> None:
    """Create the storage buckets used for uploads if they don't exist yet.

    Safe to call on every cold start; idempotent (ignores "already exists").
    """
    client = get_supabase()
    existing = {b.name for b in client.storage.list_buckets()}
    for bucket, public in ((AVATAR_BUCKET, True), (COVER_BUCKET, True)):
        if bucket not in existing:
            try:
                client.storage.create_bucket(bucket, options={"public": public})
            except Exception:
                pass
