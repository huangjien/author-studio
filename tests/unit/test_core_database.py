import asyncio
import importlib
import os
from types import SimpleNamespace

import pytest


def test_init_db_without_aiosqlite(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    os.environ["DATA_DIR"] = str(data_dir)

    import src.core.database as db

    importlib.reload(db)

    # Simulate aiosqlite unavailable
    monkeypatch.setattr(db, "_aiosqlite", None, raising=True)

    # Should create directory and return without errors
    asyncio.run(db.init_db())
    assert data_dir.exists()


def test_get_db_raises_without_aiosqlite(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    os.environ["DATA_DIR"] = str(data_dir)

    import src.core.database as db

    importlib.reload(db)

    monkeypatch.setattr(db, "_aiosqlite", None, raising=True)

    with pytest.raises(RuntimeError):
        asyncio.run(db.get_db().__anext__())


def test_ensure_db_ready_sync_no_aiosqlite(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    os.environ["DATA_DIR"] = str(data_dir)
    import src.core.database as db

    importlib.reload(db)
    monkeypatch.setattr(db, "_aiosqlite", None, raising=True)
    # Should not raise
    db.ensure_db_ready_sync()
    assert data_dir.exists()


def test_init_and_get_db_with_fake_aiosqlite(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    os.environ["DATA_DIR"] = str(data_dir)

    import src.core.database as db

    importlib.reload(db)

    class FakeConn:
        def __init__(self):
            self.executed = []
            self.committed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, sql):
            self.executed.append(sql)

        async def commit(self):
            self.committed = True

    class FakeAioSqlite:
        Row = SimpleNamespace()  # just a placeholder

        @staticmethod
        def connect(path):
            return FakeConn()

    monkeypatch.setattr(db, "_aiosqlite", FakeAioSqlite, raising=True)

    # init_db should set up directory and touch DB via connect()
    asyncio.run(db.init_db())
    assert (data_dir).exists()

    async def _consume():
        gen = db.get_db()
        conn = await gen.__anext__()
        # Ensure PRAGMA executed before yielding
        assert any("PRAGMA foreign_keys=ON" in s for s in conn.executed)
        await gen.aclose()

    asyncio.run(_consume())
