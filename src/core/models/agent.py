from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Agent(BaseModel):
    agent_id: str
    llm_config: Dict[str, Any]
    workflow: Dict[str, Any]
    prompts: Optional[Dict[str, Any]] = None
    tools: Optional[List[str]] = None
    mcp_servers: Optional[List[Dict[str, Any]]] = None
