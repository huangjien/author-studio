from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.api.routes.knowledge as knowledge


def build_app():
    app = FastAPI()
    app.include_router(knowledge.router, prefix="/api")
    return app


def test_create_knowledge_missing_fields_returns_400():
    app = build_app()
    client = TestClient(app)
    resp = client.post("/api/knowledge", json={"title": "Only title"})
    assert resp.status_code == 400
    assert "Missing required fields" in resp.json().get("detail", "")


def test_create_knowledge_tags_type_error_returns_400():
    app = build_app()
    client = TestClient(app)
    resp = client.post(
        "/api/knowledge",
        json={"title": "t", "content": "c", "tags": "not-a-list"},
    )
    assert resp.status_code == 400
    assert "tags must be a list" in resp.json().get("detail", "")


def test_create_knowledge_success(monkeypatch):
    class FakeService:
        async def create_entry(self, title, content, author=None, tags=None):
            return {
                "title": title,
                "content": content,
                "author": author,
                "tags": tags or [],
                "id": "1",
            }

    monkeypatch.setattr(knowledge, "_service", FakeService())
    app = build_app()
    client = TestClient(app)
    resp = client.post(
        "/api/knowledge",
        json={"title": "t", "content": "c", "author": "a", "tags": ["x"]},
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "ok"
    assert body["entry"]["title"] == "t"


def test_create_knowledge_exception_returns_500(monkeypatch):
    class BadService:
        async def create_entry(self, title, content, author=None, tags=None):
            raise RuntimeError("db down")

    monkeypatch.setattr(knowledge, "_service", BadService())
    app = build_app()
    client = TestClient(app)
    resp = client.post(
        "/api/knowledge",
        json={"title": "t", "content": "c"},
    )
    assert resp.status_code == 500
    assert "db down" in resp.json().get("detail", "")


def test_search_knowledge_success(monkeypatch):
    class FakeService:
        async def search(self, query, top_n=5, min_score=0.0):
            return [
                {"title": "A", "content": "...", "score": 0.9},
                {"title": "B", "content": "...", "score": 0.8},
            ]

    monkeypatch.setattr(knowledge, "_service", FakeService())
    app = build_app()
    client = TestClient(app)
    resp = client.get("/api/knowledge/search", params={"q": "alpha", "top_n": 2})
    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "ok"
    assert body["query"] == "alpha"
    assert len(body["results"]) == 2


def test_search_knowledge_exception_returns_500(monkeypatch):
    class BadService:
        async def search(self, query, top_n=5, min_score=0.0):
            raise RuntimeError("search failed")

    monkeypatch.setattr(knowledge, "_service", BadService())
    app = build_app()
    client = TestClient(app)
    resp = client.get("/api/knowledge/search", params={"q": "alpha"})
    assert resp.status_code == 500
    assert "search failed" in resp.json().get("detail", "")
