import asyncio
import os
from typing import AsyncGenerator

try:
    import aiosqlite as _aiosqlite
except Exception:  # pragma: no cover - optional import for environments without aiosqlite
    _aiosqlite = None

DEFAULT_DB_PATH = os.getenv("DATA_DIR", ".data")
DB_FILE = os.path.join(DEFAULT_DB_PATH, "app.db")


async def init_db() -> None:
    """Ensure the SQLite database file and directory exist.
    If aiosqlite is unavailable, this becomes a no-op.
    """
    os.makedirs(DEFAULT_DB_PATH, exist_ok=True)
    if _aiosqlite is None:
        return
    # Touch the DB file by opening a connection once
    async with _aiosqlite.connect(DB_FILE) as db:
        # Foreign keys off by default; enable for integrity
        await db.execute("PRAGMA foreign_keys=ON;")
        await db.commit()


async def get_db() -> AsyncGenerator:
    """Async generator yielding a connected aiosqlite DB instance.
    Raises at call-time if aiosqlite is not available.
    """
    await init_db()
    if _aiosqlite is None:
        raise RuntimeError("aiosqlite is not installed")
    async with _aiosqlite.connect(DB_FILE) as db:
        db.row_factory = _aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON;")
        yield db


async def run_migrations() -> None:
    """Placeholder for future migrations."""
    await init_db()


# Convenience synchronous initializer for startup hooks
def ensure_db_ready_sync() -> None:
    asyncio.run(init_db())
