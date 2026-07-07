"""Premium entitlement — server-side source of truth for `is_premium`.

Two entry points, per api-doc.md v1.1:
- `process_webhook` handles RevenueCat's server→server events (authoritative).
- `sync_premium` is the client-triggered fallback that queries RevenueCat's REST
  API directly to cover webhook lag right after a purchase/restore.
"""

import logging
from datetime import UTC, datetime

from app.config import get_settings
from app.core.exceptions import BadGatewayError, UnauthorizedError
from app.db.container import get_repositories
from app.models.premium import RevenueCatWebhook
from app.services import revenuecat_service

logger = logging.getLogger("premium")

# event.type → whether it grants (True) or revokes (False) premium. Anything not
# listed here (e.g. CANCELLATION) is a no-op: access runs to period end and a
# later EXPIRATION event flips it off.
_GRANT_TYPES = {"INITIAL_PURCHASE", "RENEWAL", "UNCANCELLATION", "NON_RENEWING_PURCHASE"}
_REVOKE_TYPES = {"EXPIRATION"}


def _verify_secret(authorization: str | None) -> None:
    secret = get_settings().revenuecat_webhook_secret
    if not secret:
        # Misconfiguration: never process unauthenticated webhooks.
        raise UnauthorizedError("Webhook is not configured")
    if authorization not in (secret, f"Bearer {secret}"):
        raise UnauthorizedError("Invalid webhook signature")


def _premium_until_iso(expiration_at_ms: int | None) -> str | None:
    if not expiration_at_ms:
        return None
    dt = datetime.fromtimestamp(expiration_at_ms / 1000, tz=UTC)
    return dt.isoformat().replace("+00:00", "Z")


def process_webhook(authorization: str | None, payload: RevenueCatWebhook) -> dict:
    _verify_secret(authorization)
    repos = get_repositories()
    event = payload.event
    settings = get_settings()

    # Idempotent by event.id — a redelivered event is a no-op.
    if event.id and repos.webhook_events.was_processed(event.id):
        return {}

    def _finish(reason: str = "") -> dict:
        if event.id:
            repos.webhook_events.mark_processed(event.id)
        if reason:
            logger.info("RevenueCat webhook %s no-op: %s", event.id, reason)
        return {}

    # Ignore sandbox traffic in production deployments.
    if settings.environment == "production" and event.environment == "SANDBOX":
        return _finish("sandbox event in production")

    # Only the configured premium entitlement matters.
    entitlement_ids = event.entitlement_ids or []
    if settings.revenuecat_entitlement_id not in entitlement_ids:
        return _finish("event does not concern the premium entitlement")

    if event.type in _GRANT_TYPES:
        is_premium = True
    elif event.type in _REVOKE_TYPES:
        is_premium = False
    else:
        return _finish(f"unhandled event type {event.type}")

    # app_user_id is our user UUID (set via Purchases.logIn on the client).
    user = repos.users.get_by_id(event.app_user_id) if event.app_user_id else None
    if not user:
        # Never make RevenueCat retry forever for an account we don't recognise.
        return _finish(f"unknown app_user_id {event.app_user_id}")

    fields: dict = {"is_premium": is_premium}
    fields["premium_until"] = _premium_until_iso(event.expiration_at_ms) if is_premium else None
    repos.users.update(user["id"], fields)
    return _finish()


def sync_premium(user_id: str) -> dict:
    """Reconcile `is_premium` from RevenueCat's REST API (client fallback)."""
    repos = get_repositories()
    try:
        is_premium, premium_until = revenuecat_service.fetch_premium_status(user_id)
    except revenuecat_service.RevenueCatUnavailable as exc:
        raise BadGatewayError("Could not reach the subscription service") from exc

    repos.users.update(user_id, {"is_premium": is_premium, "premium_until": premium_until})
    return {"is_premium": is_premium, "premium_until": premium_until}
