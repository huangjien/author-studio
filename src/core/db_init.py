"""
Database initialization script for core tables.

This script ensures the SQLite database exists and initializes
application tables used by services, including:
- knowledge_entries (KnowledgeService)
- sessions (SQLiteStore)

Usage:
    python -m src.core.db_init
or:
    python src/core/db_init.py
"""

import asyncio

from src.core.database import init_db


async def init_all_tables() -> None:
    """Initialize core application tables.

    - Ensures the database directory/file exists.
    - Initializes tables managed by services, if available.
    """
    # Ensure DB file/dir exists (no-op if aiosqlite not installed)
    await init_db()

    # Initialize knowledge store tables
    try:
        from src.services.knowledge_service import (  # lazy import to avoid tight coupling
            KnowledgeService,
        )

        ks = KnowledgeService()
        await ks.init_tables()
    except Exception:
        # Gracefully continue if service unavailable or optional deps missing
        # (e.g., aiosqlite not installed in the environment)
        pass

    # Initialize session persistence tables
    try:
        from src.services.persistence import SQLiteStore  # lazy import

        store = SQLiteStore()
        await store.init()
    except Exception:
        # Optional dependency; continue without failing
        pass


def main() -> None:
    asyncio.run(init_all_tables())


if __name__ == "__main__":
    main()  # pragma: no cover
