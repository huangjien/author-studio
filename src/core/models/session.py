from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class Session(BaseModel):
    session_id: str
    agent_id: str
    created_at: datetime
    history: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "active"
