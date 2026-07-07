from datetime import UTC, datetime


def _create_book(client, auth, **overrides):
    payload = {"title": "Dune", "author": "Herbert", "total_pages": 400}
    payload.update(overrides)
    return client.post("/api/v1/books", headers=auth["headers"], json=payload).json()["data"]


def test_signup_stores_yearly_goal(client):
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "goal@bookworm.app",
            "password": "hunter2a",
            "display_name": "Goaly",
            "yearly_goal_books": 24,
        },
    )
    assert resp.status_code == 201
    headers = {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}
    me = client.get("/api/v1/users/me", headers=headers).json()["data"]
    assert me["yearly_goal_books"] == 24


def test_signup_yearly_goal_defaults_to_12(client, auth):
    me = client.get("/api/v1/users/me", headers=auth["headers"]).json()["data"]
    assert me["yearly_goal_books"] == 12
    assert me["daily_goal_pages"] == 10
    assert me["reminder_time"] == "20:00"
    assert me["premium_until"] is None


def test_signup_yearly_goal_out_of_range_422(client):
    resp = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "bad@bookworm.app",
            "password": "hunter2a",
            "display_name": "Bad",
            "yearly_goal_books": 0,
        },
    )
    assert resp.status_code == 422


def test_patch_goal_fields(client, auth):
    resp = client.patch(
        "/api/v1/users/me",
        headers=auth["headers"],
        json={"daily_goal_pages": 20, "yearly_goal_books": 24, "reminder_time": "21:30"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["daily_goal_pages"] == 20
    assert data["yearly_goal_books"] == 24
    assert data["reminder_time"] == "21:30"


def test_patch_bad_reminder_time_422(client, auth):
    resp = client.patch(
        "/api/v1/users/me", headers=auth["headers"], json={"reminder_time": "9:5"}
    )
    assert resp.status_code == 422


def test_patch_daily_goal_out_of_range_422(client, auth):
    resp = client.patch(
        "/api/v1/users/me", headers=auth["headers"], json={"daily_goal_pages": 999}
    )
    assert resp.status_code == 422


def test_public_profile_excludes_goals(client, auth):
    resp = client.get(f"/api/v1/users/{auth['user']['id']}", headers=auth["headers"])
    data = resp.json()["data"]
    assert "daily_goal_pages" not in data
    assert "yearly_goal_books" not in data
    assert "reminder_time" not in data
    assert "premium_until" not in data


def test_dashboard_has_goal_ring_fields(client, auth):
    client.patch("/api/v1/users/me", headers=auth["headers"], json={"daily_goal_pages": 20})
    book = _create_book(client, auth)
    client.post(
        f"/api/v1/books/{book['id']}/progress",
        headers=auth["headers"],
        json={"pages_read": 25},
    )
    data = client.get("/api/v1/stats/dashboard", headers=auth["headers"]).json()["data"]
    assert data["daily_goal_pages"] == 20
    assert data["pages_today"] == 25
    assert data["daily_goal_met"] is True
    assert data["books_this_year"] == 0


def test_wrapped_current_month(client, auth):
    book = _create_book(client, auth, genre="sci-fi")
    client.post(
        f"/api/v1/books/{book['id']}/progress",
        headers=auth["headers"],
        json={"pages_read": 40},
    )
    client.post(
        f"/api/v1/books/{book['id']}/finish",
        headers=auth["headers"],
        json={"summary": "done", "rating": 5},
    )
    resp = client.get("/api/v1/stats/wrapped", headers=auth["headers"])
    assert resp.status_code == 200
    data = resp.json()["data"]
    month = datetime.now(UTC).strftime("%Y-%m")
    assert data["month"] == month
    assert data["books_finished"] == 1
    assert data["pages_read"] == 40
    assert data["reading_days"] == 1
    assert data["top_genre"] == "sci-fi"
    assert data["stage_delta"] == 0


def test_wrapped_bad_month_422(client, auth):
    resp = client.get("/api/v1/stats/wrapped?month=2026-13", headers=auth["headers"])
    assert resp.status_code == 422


def test_wrapped_future_month_422(client, auth):
    resp = client.get("/api/v1/stats/wrapped?month=2099-01", headers=auth["headers"])
    assert resp.status_code == 422
