"""RevenueCat REST API client.

Used by `POST /users/me/premium/sync` as a fallback when the webhook lags: the
server asks RevenueCat directly whether the caller currently holds the premium
entitlement, so the client's purchase payload is never trusted.
"""

import logging
from datetime import UTC

import httpx

from app.config import get_settings
from app.core.timeutils import parse_dt

logger = logging.getLogger("revenuecat")

_BASE_URL = "https://api.revenuecat.com/v1"


class RevenueCatUnavailable(Exception):
    """RevenueCat could not be reached / returned an unexpected response."""


def fetch_premium_status(user_id: str) -> tuple[bool, str | None]:
    """Return `(is_premium, premium_until_iso)` for the given app user.

    `premium_until` is `None` for a lifetime entitlement. Raises
    `RevenueCatUnavailable` on transport/HTTP errors so the caller can surface a
    `502` and let the client retry with backoff.
    """
    settings = get_settings()
    if not settings.revenuecat_api_key:
        raise RevenueCatUnavailable("RevenueCat API key is not configured")

    try:
        resp = httpx.get(
            f"{_BASE_URL}/subscribers/{user_id}",
            headers={"Authorization": f"Bearer {settings.revenuecat_api_key}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001 - any failure means "try again later"
        logger.warning("RevenueCat lookup failed for %s: %s", user_id, exc)
        raise RevenueCatUnavailable(str(exc)) from exc

    entitlements = (payload.get("subscriber") or {}).get("entitlements") or {}
    entitlement = entitlements.get(settings.revenuecat_entitlement_id)
    if not entitlement:
        return False, None

    expires = entitlement.get("expires_date")  # ISO-8601 or null (lifetime)
    if expires is None:
        return True, None

    from datetime import datetime

    expires_dt = parse_dt(expires)
    is_active = expires_dt > datetime.now(UTC)
    return is_active, parse_dt(expires).isoformat().replace("+00:00", "Z")
