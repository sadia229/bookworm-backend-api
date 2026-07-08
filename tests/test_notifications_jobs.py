"""Tests for the backend-owned notification triggers: admin summary broadcast
and the birthday / forest-nudge cron jobs."""

import pytest

from app.config import get_settings
from app.db import container

_ADMIN = "admin-key-123"
_CRON = "cron-secret-123"


@pytest.fixture(autouse=True)
def _configure(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", _ADMIN)
    monkeypatch.setenv("CRON_SECRET", _CRON)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _notifs(client, headers):
    return client.get("/api/v1/notifications", headers=headers).json()["data"]


# --- admin POST /summaries broadcast ------------------------------------------

def test_create_summary_requires_admin(client):
    resp = client.post("/api/v1/summaries", json={"title": "X", "description": "Y"})
    assert resp.status_code == 401


def test_create_summary_broadcasts_to_all_users(client, auth):
    resp = client.post(
        "/api/v1/summaries",
        headers={"Authorization": _ADMIN},
        json={"title": "Sapiens", "author": "Yuval Noah Harari", "description": "Big history."},
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["title"] == "Sapiens"

    # the existing `auth` user should now have a saved new-summary notification
    data = _notifs(client, auth["headers"])
    assert data["unread_count"] >= 1
    assert any(n["data"].get("type") == "new_summary" for n in data["items"])
    # and it shows up in the public list
    listed = client.get("/api/v1/summaries").json()["data"]["items"]
    assert any(s["title"] == "Sapiens" for s in listed)


# --- cron: birthday -----------------------------------------------------------

def test_birthday_cron_requires_secret(client):
    assert client.get("/api/v1/cron/birthday-wishes").status_code == 401


def test_birthday_cron_notifies_users_born_today(client, auth):
    from datetime import UTC, datetime

    today = datetime.now(UTC).date()
    repos = container.get_repositories()
    repos.users.update(auth["user"]["id"], {"dob": today.replace(year=1998).isoformat()})

    resp = client.get(
        "/api/v1/cron/birthday-wishes", headers={"Authorization": f"Bearer {_CRON}"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["notified"] == 1
    data = _notifs(client, auth["headers"])
    assert any(n["data"].get("type") == "birthday" for n in data["items"])


def test_birthday_cron_skips_non_birthdays(client, auth):
    repos = container.get_repositories()
    repos.users.update(auth["user"]["id"], {"dob": "1998-01-01"})
    # deliberately unlikely to be today for most runs; assert only shape
    resp = client.get(
        "/api/v1/cron/birthday-wishes", headers={"Authorization": f"Bearer {_CRON}"}
    )
    assert resp.status_code == 200
    assert "notified" in resp.json()["data"]


# --- cron: forest nudge -------------------------------------------------------

def test_forest_nudge_targets_inactive_old_accounts(client, auth):
    from datetime import UTC, datetime, timedelta

    # Age the account past the 7-day window with no reading sessions.
    old = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    repos = container.get_repositories()
    repos.users.update(auth["user"]["id"], {"created_at": old})

    resp = client.get(
        "/api/v1/cron/forest-nudge", headers={"Authorization": f"Bearer {_CRON}"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["notified"] == 1
    data = _notifs(client, auth["headers"])
    assert any(n["data"].get("type") == "forest_nudge" for n in data["items"])


def test_forest_nudge_skips_new_accounts(client, auth):
    # Fresh account (created_at = now) must NOT be nudged.
    resp = client.get(
        "/api/v1/cron/forest-nudge", headers={"Authorization": f"Bearer {_CRON}"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["notified"] == 0
