import pytest
from fastapi.testclient import TestClient

from src.main import app

# Detect aiosqlite availability but do not skip; we'll patch a fallback service if missing
try:
    import aiosqlite  # noqa: F401

    AIOSQLITE_AVAILABLE = True
except Exception:
    AIOSQLITE_AVAILABLE = False


# In-memory fallback KnowledgeService to exercise API endpoints when aiosqlite is unavailable
class InMemoryKnowledgeService:
    def __init__(self):
        self._entries = []
        self._next_id = 1

    async def init_tables(self):
        return None

    async def create_entry(self, title: str, content: str, author: str = None, tags=None):
        eid = self._next_id
        self._next_id += 1
        entry = {
            "id": eid,
            "title": title,
            "content": content,
            "author": author,
            "tags": tags or [],
        }
        self._entries.append(entry)
        return entry

    async def search(self, query: str, top_n: int = 5, min_score: float = 0.0):
        qlower = (query or "").lower()
        results = []
        for entry in self._entries:
            text = f"{entry.get('title', '')} {entry.get('content', '')}".lower()
            tag_text = " ".join(entry.get("tags") or []).lower()
            hit = (qlower in text) or (qlower in tag_text)
            score = 1.0 if hit else 0.0
            results.append({**entry, "score": float(score)})
        results = [r for r in results if r["score"] >= min_score]
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_n]


@pytest.fixture(autouse=True)
def mock_embeddings(monkeypatch):
    async def _fake_embed(text: str):
        # Deterministic small vector for tests
        return [0.1, 0.2, 0.3, 0.4]

    monkeypatch.setattr(
        "src.services.embedding_service.EmbeddingService.embed",
        _fake_embed,
        raising=True,
    )


@pytest.fixture(autouse=True)
def patch_knowledge_service(monkeypatch):
    if not AIOSQLITE_AVAILABLE:
        import src.api.routes.knowledge as knowledge_module

        knowledge_module._service = InMemoryKnowledgeService()


def test_create_knowledge_entry_success():
    with TestClient(app) as client:
        payload = {
            "title": "Test Doc",
            "content": "This is a test document about FastAPI and SQLite.",
            "author": "tester",
            "tags": ["test", "fastapi"],
        }
        resp = client.post("/knowledge", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("status") == "ok"
        entry = data.get("entry")
        assert isinstance(entry, dict)
        assert entry.get("id") > 0
        assert entry.get("title") == payload["title"]
        assert entry.get("author") == payload["author"]
        assert entry.get("tags") == payload["tags"]


def test_search_knowledge_returns_results():
    with TestClient(app) as client:
        # Create two entries
        client.post(
            "/knowledge",
            json={
                "title": "Doc A",
                "content": "Python concurrency and asyncio patterns.",
                "author": "alice",
                "tags": ["python", "asyncio"],
            },
        )
        client.post(
            "/knowledge",
            json={
                "title": "Doc B",
                "content": "FastAPI testing with TestClient and pytest.",
                "author": "bob",
                "tags": ["fastapi", "testing"],
            },
        )

        # Search
        resp = client.get("/knowledge/search", params={"q": "FastAPI", "top_n": 5})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("status") == "ok"
        results = data.get("results")
        assert isinstance(results, list)
        assert len(results) >= 1
        first = results[0]
        assert "id" in first and "title" in first and "content" in first
        assert isinstance(first.get("score"), float)
