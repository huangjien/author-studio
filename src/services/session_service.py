import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.config.env import settings
from src.core.models.session import Session
from src.services.persistence import FileStore, SQLiteStore


class SessionService:
    def __init__(self):
        self.mode = settings.persistence_mode
        if self.mode == "sqlite":
            self.sqlite = SQLiteStore()
            # Minimal US2: use file-based fallback for persistence until sqlite is fully implemented
            self.file = FileStore(base_dir=settings.data_dir)
        else:
            # Use configured data_dir for file-based persistence
            self.file = FileStore(base_dir=settings.data_dir)

    async def init(self):
        if self.mode == "sqlite":
            await self.sqlite.init()

    def create_session(self, agent_id: str) -> Session:
        session = Session(
            session_id=str(uuid.uuid4()),
            agent_id=agent_id,
            created_at=datetime.now(timezone.utc),
            history=[],
            status="active",
        )
        self._persist(session)
        return session

    def continue_session(self, session_id: str) -> Optional[Session]:
        if self.mode == "sqlite":
            # For simplicity, synchronous load not implemented for sqlite here
            # US2 scope can rely on file-based persistence
            pass
        else:
            data = self.file.load(f"session_{session_id}")
            if not data:
                return None
            return Session(**data)

    def _persist(self, session: Session) -> None:
        if self.mode == "sqlite":
            # Minimal US2: store file for now; sqlite persistence will be added later
            self.file.save(f"session_{session.session_id}", json.loads(session.model_dump_json()))
        else:
            self.file.save(f"session_{session.session_id}", json.loads(session.model_dump_json()))


# Singleton instance for easy use
session_service = SessionService()
