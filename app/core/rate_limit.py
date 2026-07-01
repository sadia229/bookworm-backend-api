"""Lightweight in-process rate limiter for auth endpoints.

Per api-doc.md's documented limits (signup, login, password-reset). Backed by
an in-memory sliding window, so limits reset on cold start -- acceptable for
this project's scale and noted in the README. Swap for a shared store (e.g. a
Supabase table or Redis) if running many concurrent serverless instances.
"""

import time
from collections import defaultdict

from fastapi import Request

from app.core.exceptions import TooManyRequestsError

_buckets: dict[str, list[float]] = defaultdict(list)


def _client_key(request: Request) -> str:
    # Behind a proxy (e.g. Vercel), request.client.host is the proxy's IP and is
    # identical for every visitor, which would make all clients share one bucket.
    # Prefer the real client IP from X-Forwarded-For (first hop) when present.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return "unknown"


def rate_limit(name: str, limit: int, window_seconds: int):
    async def dependency(request: Request) -> None:
        key = f"{name}:{_client_key(request)}"
        now = time.monotonic()
        window_start = now - window_seconds
        hits = [t for t in _buckets[key] if t > window_start]
        if len(hits) >= limit:
            raise TooManyRequestsError("Too many requests. Please slow down.")
        hits.append(now)
        _buckets[key] = hits

    return dependency
