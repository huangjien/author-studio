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
import os
import re
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from src.core.i18n import get_localized_prompt
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
    """Return True if AgentChat 0.7.5 is importable or mock mode is enabled.

    In mock mode, we advertise availability so routes can proceed deterministically
    without requiring the actual AgentChat packages at runtime.
    """
    if _mock_mode_enabled():
        return True
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


def _extract_system_message_for_lang(agent: Agent, accept_language: Optional[str]) -> Optional[str]:
    """Localized system message selection.

    New behavior requested:
    - If workflow.system_message exists, it overrides everything.
    - Otherwise, choose using get_localized_prompt(prompts, Accept-Language),
      defaulting to 'en' and falling back sensibly.
    - If accept_language is None, preserve legacy priority via _extract_system_message.
    """
    # Explicit override takes precedence
    wf_msg = (agent.workflow or {}).get("system_message")
    if isinstance(wf_msg, str) and wf_msg.strip():
        return wf_msg.strip()

    # Preserve legacy behavior when no Accept-Language context is provided
    if accept_language is None:
        return _extract_system_message(agent)

    # Localize via i18n helper (default='en', fallback to first available)
    prompts = agent.prompts or {}
    _selected_key, prompt_text = get_localized_prompt(prompts, accept_language)
    if isinstance(prompt_text, str) and prompt_text.strip():
        return prompt_text.strip()

    # If nothing usable, return None
    return None


def _to_valid_agent_name(agent_id: str) -> str:
    """Return a valid Python identifier for the AssistantAgent name.

    - Replace non [0-9a-zA-Z_] characters with underscores
    - Prefix with 'assistant_' to guarantee a letter at the start
    """
    sanitized = re.sub(r"[^0-9a-zA-Z_]", "_", str(agent_id))
    return f"assistant_{sanitized}"


def _mock_mode_enabled() -> bool:
    """Check if a dedicated mock mode is enabled via environment flag."""
    flag = os.getenv("AGENTS_AUTOGEN_MOCK", "").strip().lower()
    return flag in ("1", "true", "yes", "on")


# ------------------------------
# In-memory session agent registry
# ------------------------------

# Context window configuration (env-configurable)
_CONTEXT_MAX_MESSAGES: int = int(os.getenv("AGENTS_AUTOGEN_CONTEXT_MAX_MESSAGES", "8") or "8")
_CONTEXT_MAX_CHARS: int = int(os.getenv("AGENTS_AUTOGEN_CONTEXT_MAX_CHARS", "500") or "500")


class _SessionEntry:
    def __init__(
        self,
        assistant: Any,
        agent_id: str,
        system_message: Optional[str],
        selected_language: Optional[str],
    ) -> None:
        now = datetime.now(timezone.utc)
        self.assistant = assistant
        self.agent_id = agent_id
        self.system_message = system_message
        self.selected_language = selected_language
        self.created_at = now
        self.last_used = now


_SESSION_REGISTRY: Dict[str, _SessionEntry] = {}
_SESSION_LOCK: Lock = Lock()


# TTL configuration: prefer DAYS if provided, else SECONDS, else default to 30 days
def _resolve_ttl_seconds() -> int:
    days_val = os.getenv("AGENTS_AUTOGEN_SESSION_TTL_DAYS")
    if days_val and days_val.strip():
        try:
            d = int(days_val)
            return max(1, d) * 86400
        except Exception:
            pass
    seconds_val = os.getenv("AGENTS_AUTOGEN_SESSION_TTL_SECONDS")
    if seconds_val and seconds_val.strip():
        try:
            s = int(seconds_val)
            return max(60, s)
        except Exception:
            pass
    # Default: ~30 days
    return 30 * 24 * 3600


_SESSION_TTL_SECONDS: int = _resolve_ttl_seconds()


def _registry_prune() -> None:
    """Prune expired sessions by TTL."""
    try:
        now = datetime.now(timezone.utc)
        expiry = timedelta(seconds=max(60, _SESSION_TTL_SECONDS))
        to_delete: List[str] = []
        for sid, entry in _SESSION_REGISTRY.items():
            if now - entry.last_used > expiry:
                to_delete.append(sid)
        for sid in to_delete:
            _SESSION_REGISTRY.pop(sid, None)
    except Exception:
        # best-effort cleanup; never raise
        pass


def _build_available_tools(agent: Agent) -> List[str]:
    try:
        tools = list(agent.tools or [])
        for s in agent.mcp_servers or []:
            for t in s.get("tools", []) or []:
                if t not in tools:
                    tools.append(t)
        return tools
    except Exception:
        return list(agent.tools or [])


def _build_mcp_guidelines(agent: Agent) -> str:
    """Return instruction text that nudges the assistant to emit MCP directives.

    The directive format:
    MCP_DIRECTIVE:
    {"tool": "fetch"|"web_search", "provider": "local"|"http"|"process", "arguments": { ... }}
    - Emit exactly one directive line at the END of the reply IF a tool call is needed.
    - Otherwise, omit the directive entirely.
    - provider hints: use "process" for Wikipedia-oriented web_search when available;
        use "local" for offline-only.
    - arguments should include keys such as {"url": "https://..."} for
        fetch or {"query": "...", "top_n": 3} for web_search.
    """
    tools = _build_available_tools(agent)
    if not tools:
        return (
            "When a tool call is needed, emit a final line:\n"
            'MCP_DIRECTIVE: {"tool": "fetch"|"web_search", \
                "provider": "local"|"http"|"process", "arguments": { ... }}\n'
            "If no tool is required, do not emit MCP_DIRECTIVE."
        )
    tool_list = ", ".join(sorted(set(tools)))
    return (
        "You can decide whether to call an MCP tool. Available tools: "
        f"{tool_list}. If a tool call is needed, append ONE final line:\n"
        'MCP_DIRECTIVE: {"tool": "fetch"|"web_search", \
            "provider": "local"|"http"|"process", "arguments": { ... }}\n'
        '- Prefer provider="process" for Wikipedia queries if configured.\n'
        '- Use provider="local" for offline-only usage.\n'
        '- For fetch, include {"url": "https://..."}. For web_search, \
            include {"query": "..."} and optional {"top_n": N}.\n'
        "If no tool is required, DO NOT include MCP_DIRECTIVE."
    )


def _ensure_session_assistant(
    agent: Agent,
    accept_language: Optional[str],
    session_id: Optional[str],
    agentchat: Optional[Dict[str, Any]],
) -> Tuple[Any, Optional[str], Optional[str], bool]:
    """
    Ensure an AssistantAgent exists for the given session_id.

    Returns a tuple: (assistant, system_message, selected_language, created)
    - If session_id is None, creates a fresh assistant (no registry persistence)
    - If a session exists, reuses it and ignores new Accept-Language
    """
    # Try reuse if session_id provided
    if session_id:
        with _SESSION_LOCK:
            entry = _SESSION_REGISTRY.get(session_id)
            if entry:
                entry.last_used = datetime.now(timezone.utc)
                return entry.assistant, entry.system_message, entry.selected_language, False

    # Create new assistant
    selected_language: Optional[str] = None
    system_message = _extract_system_message_for_lang(agent, accept_language)
    if accept_language is not None:
        # get_localized_prompt returns (selected, text)
        selected_language, _ = get_localized_prompt(agent.prompts or {}, accept_language)

    # Optionally append MCP routing guidelines when explicitly enabled via env
    try:
        enable_hints = os.getenv("AGENTS_AUTOGEN_MCP_HINTS", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if enable_hints:
            mcp_guidelines = _build_mcp_guidelines(agent)
            if system_message:
                system_message = system_message.strip() + "\n\n" + mcp_guidelines
            else:
                system_message = mcp_guidelines
    except Exception:
        # Non-fatal; continue without guidelines
        pass

    if _mock_mode_enabled():
        assistant = _MockAssistant(agent.agent_id)
    else:
        assert agentchat is not None
        llm_config = _to_llm_config(agent.llm_config)
        model = str(llm_config.get("model", "gpt-4o-mini"))

        Client = agentchat["OpenAIChatCompletionClient"]
        Assistant = agentchat["AssistantAgent"]

        # Pass through optional client kwargs to support non-OpenAI-compatible models
        client_kwargs: Dict[str, Any] = {}
        for k in ("api_key", "base_url", "model_info", "timeout"):
            v = llm_config.get(k)
            if v is not None:
                client_kwargs[k] = v

        provider = str(llm_config.get("provider", "")).lower()
        if provider == "deepseek":
            # Default base_url and API key for DeepSeek if not provided in llm_config
            client_kwargs.setdefault("base_url", "https://api.deepseek.com/v1")
            env_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
            if env_key and "api_key" not in client_kwargs:
                client_kwargs["api_key"] = env_key
            # Many autogen clients require a model_info when model is not an OpenAI canonical name
            client_kwargs.setdefault(
                "model_info",
                {
                    "name": model,
                    "compatibility": "openai",
                    "vision": False,
                    "function_calling": False,
                    "json_output": False,
                    "family": "deepseek",
                },
            )
        elif provider == "ollama":
            # Provide an optional base URL via environment
            # and a generic model_info to bypass name checks
            ollama_base = os.getenv("OLLAMA_BASE_URL")
            if ollama_base:
                client_kwargs.setdefault("base_url", ollama_base)
            client_kwargs.setdefault(
                "model_info",
                {
                    "name": model,
                    "compatibility": "openai",
                    "vision": False,
                    "function_calling": False,
                    "json_output": False,
                    "family": "ollama",
                },
            )

        # Ensure model_info contains required keys for autogen-ext >=0.4.7
        mi = client_kwargs.get("model_info")
        if isinstance(mi, dict):
            mi.setdefault("name", model)
            mi.setdefault("compatibility", "openai")
            mi.setdefault("vision", False)
            mi.setdefault("function_calling", False)
            mi.setdefault("json_output", False)
            mi.setdefault("family", provider if provider else "openai")

        client = Client(model=model, **client_kwargs)

        assistant_kwargs: Dict[str, Any] = {
            "name": _to_valid_agent_name(agent.agent_id),
            "model_client": client,
        }
        if system_message:
            assistant_kwargs["system_message"] = system_message

        assistant = Assistant(**assistant_kwargs)

    # Persist into registry if session_id present
    created = True
    if session_id:
        with _SESSION_LOCK:
            _SESSION_REGISTRY[session_id] = _SessionEntry(
                assistant=assistant,
                agent_id=agent.agent_id,
                system_message=system_message,
                selected_language=selected_language,
            )
    # Opportunistic prune
    _registry_prune()

    return assistant, system_message, selected_language, created


def _format_history_context(
    history: Optional[List[Dict[str, Any]]],
) -> Optional[str]:
    """Format prior session history into a compact textual context block.

    This is a pragmatic approach to multi-turn memory when the underlying assistant
    does not maintain conversation state between calls. It ensures continuity by
    prepending a recent transcript to the current task.
    """
    if not history:
        return None
    try:
        # Take the last N messages
        recent = history[-_CONTEXT_MAX_MESSAGES:]
        lines: List[str] = []
        lines.append(f"Conversation context (last {len(recent)} messages):")
        for msg in recent:
            role = str(msg.get("role") or "unknown")
            content = str(msg.get("content") or "")
            truncated = content[:_CONTEXT_MAX_CHARS]
            if len(content) > _CONTEXT_MAX_CHARS:
                truncated = truncated + "…"
            # Normalize role labeling
            if role == "agent":
                role = "assistant"
            elif role not in ("user", "assistant"):
                role = "other"
            lines.append(f"- {role}: {truncated}")
        return "\n".join(lines)
    except Exception:
        return None


def _compose_task(user_input: str, history: Optional[List[Dict[str, Any]]]) -> str:
    context = _format_history_context(history)
    if context:
        return f"{context}\n\nCurrent request:\n{user_input}"
    return user_input


# Minimal mock Assistant to mirror interface for tests when AGENTS_AUTOGEN_MOCK=1
class _MockAssistant:
    def __init__(self, agent_id: str) -> None:
        self.name = _to_valid_agent_name(agent_id)

    async def run(self, task: str) -> str:
        # Deterministic echo for testing parity
        await asyncio.sleep(0)
        return f"Echo: {task}"


# -------------
# Public API
# -------------


def _mock_result(agent: Agent, user_input: str) -> Dict[str, Any]:
    """Produce a deterministic echo result used in test or mock environments."""
    llm_config = _to_llm_config(agent.llm_config)
    return {
        "ok": True,
        "agent_id": agent.agent_id,
        "input": user_input,
        "llm_config": llm_config,
        "chat_result": f"Echo: {user_input} (agent={agent.agent_id})",
        "flavor": "agentchat-0.7.5-mock",
    }


def run_single_turn(
    agent: Agent,
    user_input: str,
    accept_language: Optional[str] = None,
    session_id: Optional[str] = None,
    session_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run a single-turn AutoGen conversation using AgentChat 0.7.5.

    Returns a structured dict summarizing the result, or an error if AgentChat
    is not available.
    """
    # Compose task with context regardless of mock mode
    composed_task = _compose_task(user_input, session_history)

    if _mock_mode_enabled():
        return _mock_result(agent, composed_task)

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
        assistant, _system_message, selected_language, _created = _ensure_session_assistant(
            agent=agent,
            accept_language=accept_language,
            session_id=session_id,
            agentchat=agentchat,
        )
        # AgentChat `run` is async; use asyncio.run in synchronous contexts
        result_text = asyncio.run(assistant.run(task=composed_task))

        llm_config = _to_llm_config(agent.llm_config)
        return {
            "ok": True,
            "agent_id": agent.agent_id,
            "input": composed_task,
            "llm_config": llm_config,
            "chat_result": str(result_text),
            "flavor": "agentchat-0.7.5",
            "session_selected_language": selected_language,
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
    return _import_agentchat() is not None or _mock_mode_enabled()


async def run_single_turn_async(
    agent: Agent,
    user_input: str,
    accept_language: Optional[str] = None,
    session_id: Optional[str] = None,
    session_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Async variant of single-turn conversation using AgentChat 0.7.5.

    Returns the same structured dict as `run_single_turn`. If AgentChat is not available,
    returns an error dict indicating the missing dependency.
    """
    # Compose task with context regardless of mock mode
    composed_task = _compose_task(user_input, session_history)

    if _mock_mode_enabled():
        return _mock_result(agent, composed_task)

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
        assistant, _system_message, selected_language, _created = _ensure_session_assistant(
            agent=agent,
            accept_language=accept_language,
            session_id=session_id,
            agentchat=agentchat,
        )
        result_text = await assistant.run(task=composed_task)

        llm_config = _to_llm_config(agent.llm_config)
        return {
            "ok": True,
            "agent_id": agent.agent_id,
            "input": composed_task,
            "llm_config": llm_config,
            "chat_result": str(result_text),
            "flavor": "agentchat-0.7.5",
            "session_selected_language": selected_language,
        }
    except Exception as e:
        # Preserve a helpful hint and structure
        return {
            "ok": False,
            "error": f"autogen agentchat interaction failed: {e}",
            "flavor": "agentchat-0.7.5",
        }
