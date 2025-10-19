import importlib

import pytest

from src.agents.autogen_adapter import is_available, run_single_turn
from src.core.models.agent import Agent


def _has_mod(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def test_autogen_adapter_graceful_when_missing():
    """If AgentChat is not installed, the adapter should respond gracefully
    without raising."""
    if not is_available():
        agent = Agent(
            agent_id="autogen-missing",
            llm_config={"provider": "openai", "model": "gpt-4o-mini"},
            workflow={},
            prompts={},
            tools=[],
            mcp_servers=[],
        )
        result = run_single_turn(agent, "Test message")
        assert result["ok"] is False
        assert "AgentChat" in result.get("error", "")
    else:
        pytest.skip("AgentChat is installed; this test targets the missing package case.")


def test_autogen_adapter_runs_when_available():
    """If AgentChat is present, ensure the adapter executes without immediate
    failure.

    This test is skipped unless the stable AgentChat (0.7.5)
    packages are importable in the environment.
    """
    has_agentchat = _has_mod("autogen_agentchat") and _has_mod("autogen_ext.models.openai")
    if not has_agentchat:
        pytest.skip("AgentChat 0.7.5 not installed; skipping availability test.")

    agent = Agent(
        agent_id="autogen-present",
        llm_config={"provider": "openai", "model": "gpt-4o-mini"},
        workflow={},
        prompts={},
        tools=[],
        mcp_servers=[],
    )
    result = run_single_turn(agent, "Say hello in one sentence.")
    assert isinstance(result, dict)
    # We can't assert `ok` is True deterministically (depends on credentials),
    # but we can assert the adapter returned a structured dict.
    # If credentials are not present, the adapter gracefully returns an error.
    assert "ok" in result
