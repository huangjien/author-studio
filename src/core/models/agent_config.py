from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class WorkflowConfig(BaseModel):
    type: Optional[str] = None
    human_in_loop: Optional[str] = None


class AgentConfig(BaseModel):
    name: str
    llm: Dict[str, str]  # provider/model/keys/etc.
    workflow: WorkflowConfig | Dict[str, str]
    prompts: Dict[str, str]
    tools: List[str] = Field(default_factory=list)
