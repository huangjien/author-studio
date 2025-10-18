import json
import os
from typing import Any, Dict, Optional

# Optional import: degrade gracefully if aiosqlite is not available
try:
    import aiosqlite  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    aiosqlite = None

class FileStore:
    def __init__(self, base_dir: str = ".data") -> None:
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _path(self, name: str) -> str:
        return os.path.join(self.base_dir, f"{name}.json")

    def save(self, name: str, data: Dict[str, Any]) -> None:
        with open(self._path(name), "w") as f:
            json.dump(data, f)

    def load(self, name: str) -> Optional[Dict[str, Any]]:
        path = self._path(name)
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            return json.load(f)

class SQLiteStore:
    def __init__(self, db_path: str = ".data/app.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        if aiosqlite is None:
            # Mark as unavailable; callers should avoid using when dependency missing
            self._available = False
        else:
            self._available = True

    async def init(self) -> None:
        if not self._available:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    history TEXT NOT NULL
                );
                """
            )
            await db.commit()

    async def save_session(self, session_id: str, agent_id: str, status: str, history_json: str) -> None:
        if not self._available:
            return
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO sessions(session_id, agent_id, status, history) VALUES (?, ?, ?, ?)",
                (session_id, agent_id, status, history_json),
            )
            await db.commit()

    async def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        if not self._available:
            return None
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT session_id, agent_id, status, history FROM sessions WHERE session_id = ?",
                (session_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return {
                    "session_id": row[0],
                    "agent_id": row[1],
                    "status": row[2],
                    "history": json.loads(row[3]),
                }