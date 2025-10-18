from typing import Dict, List

from pydantic import BaseModel, Field


class Agent(BaseModel):
    agent_id: str
    llm_config: Dict[str, str]
    workflow: Dict[str, str]
    prompts: Dict[str, str]
    tools: List[str] = Field(default_factory=list)
