import asyncio
import pytest


class DummyExecute:
    def __init__(self, store, sql, params=None):
        self.store = store
        self.sql_upper = sql.strip().upper()
        self.params = params or []

    def __await__(self):
        async def _run():
            # Handle CREATE/INSERT in awaitable form
            if self.sql_upper.startswith("CREATE TABLE"):
                return self
            if self.sql_upper.startswith("INSERT OR REPLACE INTO SESSIONS"):
                session_id, agent_id, status, history_json = self.params
                self.store[session_id] = (
                    session_id,
                    agent_id,
                    status,
                    history_json,
                )
                return self
            # SELECT is used with async with, not awaited in our code path
            return self
        return _run().__await__()

    async def __aenter__(self):
        # For SELECT statements, return self as a cursor
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def fetchone(self):
        # Only relevant for SELECT
        if self.sql_upper.startswith("SELECT SESSION_ID"):
            session_id = self.params[0]
            return self.store.get(session_id)
        return None


class DummyConnection:
    def __init__(self, store):
        self.store = store

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        return DummyExecute(self.store, sql, params)

    async def commit(self):
        # no-op
        return None


class DummyAioSqlite:
    def __init__(self):
        self.store = {}

    def connect(self, path):
        # Return an async context manager
        return DummyConnection(self.store)


def test_sqlite_store_save_and_load(monkeypatch, tmp_path):
    # Patch aiosqlite with dummy implementation
    import src.services.persistence as persistence
    monkeypatch.setattr(persistence, "aiosqlite", DummyAioSqlite(), raising=True)

    store = persistence.SQLiteStore(db_path=str(tmp_path / "app.db"))

    async def run_flow():
        await store.init()
        await store.save_session("s1", "agent-1", "active", "[\"hello\"]")
        loaded = await store.load_session("s1")
        return loaded

    loaded = asyncio.run(run_flow())
    assert loaded is not None
    assert loaded["session_id"] == "s1"
    assert loaded["agent_id"] == "agent-1"
    assert loaded["status"] == "active"
    assert loaded["history"] == ["hello"]

    # Non-existent session returns None
    async def run_missing():
        return await store.load_session("missing")

    missing = asyncio.run(run_missing())
    assert missing is None


def test_sqlite_store_unavailable_is_noop(monkeypatch, tmp_path):
    import src.services.persistence as persistence
    # Simulate aiosqlite missing
    monkeypatch.setattr(persistence, "aiosqlite", None, raising=True)

    store = persistence.SQLiteStore(db_path=str(tmp_path / "app.db"))

    async def run_flow():
        await store.init()  # should not raise
        await store.save_session("s2", "agent-2", "active", "[]")  # should not raise
        return await store.load_session("s2")

    loaded = asyncio.run(run_flow())
    assert loaded is None