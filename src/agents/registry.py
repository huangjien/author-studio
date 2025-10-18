import logging
from typing import Dict, List, Optional

from src.agents.loader import build_agents
from src.config.loader import load_agent_configs
from src.core.models.agent import Agent
from src.core.models.agent_config import AgentConfig

logger = logging.getLogger(__name__)


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, Agent] = {}

    def load_from_configs(self, configs: List[AgentConfig]) -> None:
        logger.info("Loading agents from configs (count=%d)", len(configs))
        self._agents.clear()
        for agent in build_agents(configs):
            if agent.agent_id in self._agents:
                logger.error("Duplicate agent id '%s' encountered; skipping.", agent.agent_id)
                continue
            logger.info("Registered agent '%s'", agent.agent_id)
            self._agents[agent.agent_id] = agent
        logger.info("Agent registry loaded: %d agents", len(self._agents))

    def reload(self, dir_path: str = "agent_configs") -> None:
        logger.info("Reloading agents from directory: %s", dir_path)
        configs = load_agent_configs(dir_path=dir_path)
        self.load_from_configs(configs)

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return self._agents.get(agent_id)

    def list_agents(self) -> List[Agent]:
        return list(self._agents.values())

    def count(self) -> int:
        return len(self._agents)
