import glob
import logging
import os
from typing import List

import yaml

from src.config.validator import validate_config
from src.core.models.agent_config import AgentConfig

logger = logging.getLogger(__name__)


def load_agent_configs(dir_path: str = "agent_configs") -> List[AgentConfig]:
    """
    Read all YAML files in dir_path and return a list of validated AgentConfig instances.
    Invalid files are logged and skipped.
    """
    patterns = [os.path.join(dir_path, "*.yaml"), os.path.join(dir_path, "*.yml")]
    configs: List[AgentConfig] = []
    for pattern in patterns:
        for path in glob.glob(pattern):
            try:
                with open(path, "r") as f:
                    data = yaml.safe_load(f) or {}
            except Exception as e:
                logger.error("Failed to parse YAML file %s: %s", path, e)
                continue
            ok, errors = validate_config(data)
            if not ok:
                logger.error("Invalid agent config %s: %s", path, "; ".join(errors))
                continue
            try:
                cfg = AgentConfig(**data)
                configs.append(cfg)
            except Exception as e:
                logger.error("Failed to build AgentConfig from %s: %s", path, e)
                continue
    return configs
