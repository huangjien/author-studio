import os
import shutil
import tempfile
from typing import Any, Dict

import yaml

from src.services.tool_service import ToolNotFoundError, ToolService


def setup_env() -> str:
    temp_dir = tempfile.mkdtemp(prefix="agent_cfg_")
    cfg_path = os.path.join(temp_dir, "example_agent.yaml")
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "name": "Alpha Bot",
                "llm": {"provider": "openai", "model": "gpt-4o-mini"},
                "workflow": {"type": "simple"},
                "tools": ["web_search"],
                "mcp_servers": [
                    {"name": "local-provider", "type": "local", "tools": ["web_search"]}
                ],
            },
            f,
            sort_keys=False,
        )
    return temp_dir


def teardown_env(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


def test_tool_service_invoke_local_web_search() -> None:
    target_dir = setup_env()
    try:
        service = ToolService(dir_path=target_dir)
        result: Dict[str, Any] = service.invoke(
            agent_id="alpha-bot",
            tool_name="web_search",
            arguments={"query": "hello", "top_n": 1},
        )
        assert result["tool"] == "web_search"
        assert result["query"] == "hello"
        assert isinstance(result["results"], list)
        assert len(result["results"]) == 1
    finally:
        teardown_env(target_dir)


def test_tool_service_handles_unknown_tool() -> None:
    target_dir = setup_env()
    try:
        service = ToolService(dir_path=target_dir)
        try:
            service.invoke(agent_id="alpha-bot", tool_name="unknown_tool", arguments={})
            assert False, "Expected ToolNotFoundError"
        except ToolNotFoundError:
            assert True
    finally:
        teardown_env(target_dir)
