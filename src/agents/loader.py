import re
from typing import List

from src.core.models.agent import Agent
from src.core.models.agent_config import AgentConfig, WorkflowConfig


def _slugify(name: str) -> str:
    # Lowercase, replace non-alphanumeric with hyphens, collapse repeats, strip hyphens
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def _normalize_workflow(workflow: WorkflowConfig | dict) -> dict:
    if isinstance(workflow, WorkflowConfig):
        return workflow.model_dump()
    if isinstance(workflow, dict):
        return workflow
    return {}


def build_agent(cfg: AgentConfig) -> Agent:
    agent_id = _slugify(cfg.name)
    return Agent(
        agent_id=agent_id,
        llm_config=cfg.llm,
        workflow=_normalize_workflow(cfg.workflow),
        prompts=cfg.prompts,
        tools=cfg.tools or [],
    )


def build_agents(configs: List[AgentConfig]) -> List[Agent]:
    return [build_agent(c) for c in configs]
