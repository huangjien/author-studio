import asyncio


def test_init_all_tables_success(monkeypatch):
    from src.core import db_init as dbi

    calls = {"init_db": 0, "ks_init": 0, "store_init": 0}

    async def fake_init_db():
        calls["init_db"] += 1

    class FakeKS:
        async def init_tables(self):
            calls["ks_init"] += 1

    class FakeStore:
        async def init(self):
            calls["store_init"] += 1

    monkeypatch.setattr("src.core.db_init.init_db", fake_init_db, raising=True)
    monkeypatch.setattr("src.services.knowledge_service.KnowledgeService", FakeKS, raising=True)
    monkeypatch.setattr("src.services.persistence.SQLiteStore", FakeStore, raising=True)

    asyncio.run(dbi.init_all_tables())
    assert calls["init_db"] == 1
    assert calls["ks_init"] == 1
    assert calls["store_init"] == 1


def test_init_all_tables_handles_exceptions(monkeypatch):
    from src.core import db_init as dbi

    async def fake_init_db():
        pass

    class BadKS:
        async def init_tables(self):
            raise RuntimeError("boom")

    class BadStore:
        async def init(self):
            raise RuntimeError("boom")

    monkeypatch.setattr("src.core.db_init.init_db", fake_init_db, raising=True)
    monkeypatch.setattr("src.services.knowledge_service.KnowledgeService", BadKS, raising=True)
    monkeypatch.setattr("src.services.persistence.SQLiteStore", BadStore, raising=True)

    # Should not raise despite exceptions inside init steps
    asyncio.run(dbi.init_all_tables())


def test_db_init_main_runs(monkeypatch):
    # Ensure main() runs without raising by patching init functions to no-ops
    from src.core import db_init as dbi

    async def fake_init_db():
        pass

    class NoopKS:
        async def init_tables(self):
            pass

    class NoopStore:
        async def init(self):
            pass

    monkeypatch.setattr("src.core.db_init.init_db", fake_init_db, raising=True)
    monkeypatch.setattr("src.services.knowledge_service.KnowledgeService", NoopKS, raising=True)
    monkeypatch.setattr("src.services.persistence.SQLiteStore", NoopStore, raising=True)

    # Should complete without exceptions
    dbi.main()
