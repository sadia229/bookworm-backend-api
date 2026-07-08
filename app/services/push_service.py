"""Firebase Cloud Messaging integration.

Device tokens and notification history live in Supabase (see
`notification_service.py`); this module is only responsible for the actual
FCM send. If `FIREBASE_CREDENTIALS_JSON` isn't configured, sends are skipped
with a warning so the rest of the API keeps working in dev/CI.
"""

import json
import logging

from app.config import get_settings

logger = logging.getLogger("push_service")

_initialized = False


def _ensure_initialized() -> bool:
    global _initialized
    if _initialized:
        return True

    settings = get_settings()
    if not settings.firebase_credentials_json:
        return False

    import firebase_admin
    from firebase_admin import credentials

    try:
        if not firebase_admin._apps:
            cred_dict = json.loads(settings.firebase_credentials_json)
            firebase_admin.initialize_app(credentials.Certificate(cred_dict))
        _initialized = True
        return True
    except Exception:
        logger.exception("Failed to initialize Firebase Admin SDK")
        return False


def send_push(tokens: list[str], title: str, body: str, data: dict | None = None) -> None:
    if not tokens:
        return
    if not _ensure_initialized():
        logger.warning("Firebase not configured; skipping push send: %s", title)
        return

    from firebase_admin import messaging

    payload_data = {str(k): str(v) for k, v in (data or {}).items()}
    # FCM multicast accepts at most 500 tokens per call; chunk for broadcasts.
    for i in range(0, len(tokens), 500):
        chunk = tokens[i : i + 500]
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=payload_data,
            tokens=chunk,
        )
        try:
            messaging.send_each_for_multicast(message)
        except Exception:
            logger.exception("Failed to send FCM push notification")
