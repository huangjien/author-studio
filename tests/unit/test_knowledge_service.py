import pytest

from src.services.knowledge_service import KnowledgeService


def test_knowledge_service_init_tables_handles_no_aiosqlite(monkeypatch):
    svc = KnowledgeService()

    async def _run():
        try:
            await svc.init_tables()
        except RuntimeError as e:
            # If aiosqlite isn't installed, database helpers should raise at call-time
            assert "aiosqlite" in str(e).lower()

    import asyncio

    asyncio.run(_run())


def test_knowledge_service_create_and_search(monkeypatch):
    svc = KnowledgeService()

    async def _run():
        try:
            # Attempt table init; if aiosqlite is missing, operations below should be skipped
            await svc.init_tables()
            entry = await svc.create_entry(title="Doc1", content="Test content about Python.")
            assert entry["id"] > 0
            res = await svc.search(query="Python", top_n=3)
            assert isinstance(res, list)
            assert res and res[0]["id"] == entry["id"]
        except RuntimeError as e:
            if "aiosqlite" in str(e).lower():
                pytest.skip("aiosqlite not available")
            raise

    import asyncio

    asyncio.run(_run())
