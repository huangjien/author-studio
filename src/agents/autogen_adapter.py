"""
Optional AutoGen integration adapter (AgentChat 0.7.5 only).

This module provides a thin integration layer to run simple AutoGen conversations
using the project's existing Agent configuration structure, WITHOUT introducing a hard
runtime dependency on the AutoGen packages. If AgentChat is not installed, the
functions return informative errors so the rest of the project remains unaffected.

Usage (if AgentChat 0.7.5 is installed):

    from src.core.models.agent import Agent
    from src.agents.autogen_adapter import run_single_turn

    agent = Agent(
        agent_id="alpha",
        llm_config={"model": "gpt-4o-mini", "provider": "openai"},
        workflow={},
        prompts={},
        tools=[],
        mcp_servers=[],
    )

    result = run_single_turn(agent, "Hello! Summarize AutoGen in one sentence.")
    print(result)

Notes:
- We avoid importing AgentChat at module import time to keep tests passing even if
  the library is not present. We import inside functions when needed.
- This is a minimal, safe adapter. Expanding to multi-agent/group chat can be done
  incrementally without touching existing tested flows.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, Optional

from src.core.models.agent import Agent


def _import_agentchat():
    """Try to import the stable AgentChat + Ext OpenAI client.

    Returns a small dict with required classes if available, otherwise None.
    """
    try:
        # Stable AgentChat API (0.7.5)
        from autogen_agentchat.agents import AssistantAgent  # type: ignore
        from autogen_ext.models.openai import OpenAIChatCompletionClient  # type: ignore

        return {
            "AssistantAgent": AssistantAgent,
            "OpenAIChatCompletionClient": OpenAIChatCompletionClient,
        }
    except Exception:
        return None


def is_available() -> bool:
    """Return True if AgentChat 0.7.5 is importable."""
    return _import_agentchat() is not None


def _to_llm_config(agent_llm_config: Dict[str, Any]) -> Dict[str, Any]:
    """Map our Agent.llm_config into something AutoGen can consume.

    We pass through as-is, since AgentChat accepts a flexible `llm_config` dict.
    You may want to normalize keys like `model`, `api_key`, `base_url`, etc.
    """
    return dict(agent_llm_config or {})


def _extract_system_message(agent: Agent) -> Optional[str]:
    """Derive a system message from agent prompts or workflow config.

    Priority:
    1) workflow.system_message (explicit override)
    2) prompts.system
    3) prompts.en (common default)
    4) first value in prompts dict
    """
    wf_msg = (agent.workflow or {}).get("system_message")
    if isinstance(wf_msg, str) and wf_msg.strip():
        return wf_msg.strip()

    prompts = agent.prompts or {}
    for key in ("system", "en"):
        val = prompts.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    # fallback: first prompt value if any
    for val in prompts.values():
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _to_valid_agent_name(agent_id: str) -> str:
    """Return a valid Python identifier for the AssistantAgent name.

    - Replace non [0-9a-zA-Z_] characters with underscores
    - Prefix with 'assistant_' to guarantee a letter at the start
    """
    sanitized = re.sub(r"[^0-9a-zA-Z_]", "_", str(agent_id))
    return f"assistant_{sanitized}"


def run_single_turn(agent: Agent, user_input: str) -> Dict[str, Any]:
    """Run a single-turn AutoGen conversation using AgentChat 0.7.5.

    Returns a structured dict summarizing the result, or an error if AgentChat
    is not available.
    """
    agentchat = _import_agentchat()
    if agentchat is None:
        return {
            "ok": False,
            "error": (
                "AgentChat 0.7.5 is not installed. Install with `pip install .[autogen-stable]` "
                'or `pip install "autogen-agentchat==0.7.5" "autogen-ext[openai,mcp]==0.7.5"`.'
            ),
            "flavor": "agentchat-0.7.5",
        }

    try:
        llm_config = _to_llm_config(agent.llm_config)
        model = str(llm_config.get("model", "gpt-4o-mini"))

        # Construct a simple AssistantAgent backed by OpenAI chat completion client
        Client = agentchat["OpenAIChatCompletionClient"]
        Assistant = agentchat["AssistantAgent"]
        client = Client(model=model)

        assistant_kwargs: Dict[str, Any] = {
            "name": _to_valid_agent_name(agent.agent_id),
            "model_client": client,
        }
        system_message = _extract_system_message(agent)
        if system_message:
            assistant_kwargs["system_message"] = system_message

        assistant = Assistant(**assistant_kwargs)
        # AgentChat `run` is async; use asyncio.run in synchronous contexts
        result_text = asyncio.run(assistant.run(task=user_input))

        return {
            "ok": True,
            "agent_id": agent.agent_id,
            "input": user_input,
            "llm_config": llm_config,
            "chat_result": str(result_text),
            "flavor": "agentchat-0.7.5",
        }
    except Exception as e:
        # Preserve a helpful hint and structure
        return {
            "ok": False,
            "error": f"autogen agentchat interaction failed: {e}",
            "flavor": "agentchat-0.7.5",
        }


# Async support for web contexts (AgentChat 0.7.5)


def supports_agentchat_async() -> bool:
    """Return True if the AgentChat 0.7.5 stack is available.

    This indicates the adapter can run without `asyncio.run`, suitable for async endpoints.
    """
    return _import_agentchat() is not None


async def run_single_turn_async(agent: Agent, user_input: str) -> Dict[str, Any]:
    """Async variant of single-turn conversation using AgentChat 0.7.5.

    Returns the same structured dict as `run_single_turn`. If AgentChat is not available,
    returns an error dict indicating the missing dependency.
    """
    agentchat = _import_agentchat()
    if agentchat is None:
        return {
            "ok": False,
            "error": (
                "AgentChat 0.7.5 is not installed. Install with `pip install .[autogen-stable]` "
                'or `pip install "autogen-agentchat==0.7.5" "autogen-ext[openai,mcp]==0.7.5"`.'
            ),
            "flavor": "agentchat-0.7.5",
        }

    try:
        llm_config = _to_llm_config(agent.llm_config)
        model = str(llm_config.get("model", "gpt-4o-mini"))

        Client = agentchat["OpenAIChatCompletionClient"]
        Assistant = agentchat["AssistantAgent"]
        client = Client(model=model)

        assistant_kwargs: Dict[str, Any] = {
            "name": _to_valid_agent_name(agent.agent_id),
            "model_client": client,
        }
        system_message = _extract_system_message(agent)
        if system_message:
            assistant_kwargs["system_message"] = system_message

        assistant = Assistant(**assistant_kwargs)
        result_text = await assistant.run(task=user_input)

        return {
            "ok": True,
            "agent_id": agent.agent_id,
            "input": user_input,
            "llm_config": llm_config,
            "chat_result": str(result_text),
            "flavor": "agentchat-0.7.5",
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"autogen agentchat interaction failed: {e}",
            "flavor": "agentchat-0.7.5",
        }
