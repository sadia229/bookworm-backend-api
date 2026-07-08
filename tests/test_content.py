def test_quotes_public_no_auth(client):
    resp = client.get("/api/v1/quotes")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 1
    assert {"id", "text", "author", "category"} <= set(data[0].keys())


def test_quotes_category_filter(client):
    resp = client.get("/api/v1/quotes?category=Romance")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert all(q["category"] == "Romance" for q in data)


def test_quotes_limit(client):
    resp = client.get("/api/v1/quotes?limit=1")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


def test_quotes_bad_category_422(client):
    resp = client.get("/api/v1/quotes?category=Horror")
    assert resp.status_code == 422


def test_quotes_bad_limit_422(client):
    resp = client.get("/api/v1/quotes?limit=0")
    assert resp.status_code == 422


def test_summaries_public_paginated(client):
    resp = client.get("/api/v1/summaries")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert {"items", "page", "size", "total"} <= set(data.keys())
    assert len(data["items"]) >= 1
    assert {"id", "title", "description", "contributor"} <= set(data["items"][0].keys())


def test_summaries_pagination(client):
    resp = client.get("/api/v1/summaries?page=1&size=1")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["size"] == 1
    assert len(data["items"]) == 1


def test_summaries_bad_size_422(client):
    resp = client.get("/api/v1/summaries?size=999")
    assert resp.status_code == 422
