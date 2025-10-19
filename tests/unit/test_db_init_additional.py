import asyncio
import sys
import types

from src.core import db_init


def test_init_all_tables_fallback_on_knowledge_service_error(monkeypatch):
    # Provide a fake knowledge_service module whose class raises at init_tables
    fake_ks_mod = types.ModuleType("src.services.knowledge_service")

    class KS:
        async def init_tables(self):
            raise RuntimeError("boom")

    fake_ks_mod.KnowledgeService = KS  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "src.services.knowledge_service", fake_ks_mod)

    # Provide a fake persistence module whose SQLiteStore raises at init
    fake_pers_mod = types.ModuleType("src.services.persistence")

    class Store:
        async def init(self):
            raise RuntimeError("boom")

    fake_pers_mod.SQLiteStore = Store  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "src.services.persistence", fake_pers_mod)

    # Run init_all_tables; it should catch exceptions and continue
    asyncio.run(db_init.init_all_tables())


def test_db_init_main_runs_event_loop(monkeypatch):
    # Spy on init_all_tables to ensure it is called by main()
    calls = {"count": 0}

    async def spy():
        calls["count"] += 1

    monkeypatch.setattr(db_init, "init_all_tables", spy)
    db_init.main()
    assert calls["count"] == 1
