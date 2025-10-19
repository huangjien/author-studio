import re
from typing import Optional

from src.agents.registry import AgentRegistry
from src.core.i18n import get_localized_prompt
from src.services.cache import memoize
from src.services.session_service import session_service
from src.services.tool_service import ToolNotFoundError, ToolService

# For testing and observability of caching behavior
compute_output_call_count = 0


@memoize
def compute_output(
    agent_id: str,
    input_text: str,
    selected_lang: str,
    prompt_text: Optional[str],
) -> str:
    global compute_output_call_count
    compute_output_call_count += 1
    prefix = prompt_text or ""
    if prefix:
        return f"[{agent_id}] {prefix} :: Echo: {input_text}"
    else:
        return f"[{agent_id}] Echo: {input_text}"


def _agent_supports_tool(agent, tool_name: str) -> bool:
    try:
        # Prefer aggregated tool listing via ToolService to handle duplicate YAML files
        service = ToolService()
        listed = service.list_tools(agent.agent_id)
        tools = listed.get("tools") if isinstance(listed, dict) else None
        if isinstance(tools, list) and tool_name in tools:
            return True
    except Exception:
        # Fall back to direct inspection if list_tools fails
        pass
    try:
        tools = agent.tools or []
        server_tools = []
        for s in agent.mcp_servers or []:
            server_tools.extend(s.get("tools") or [])
        return tool_name in tools or tool_name in server_tools
    except Exception:
        return False


def _sanitize_url(u: str) -> str:
    # Strip surrounding whitespace and common wrapping punctuation/backticks
    if not isinstance(u, str):
        return ""
    u = u.strip()
    # Remove trailing wrapper chars often used in markdown/code blocks
    u = re.sub(r"[`\"'()\[\]<>.,;]+$", "", u)
    # Remove leading wrapper chars similarly
    u = re.sub(r"^['`\"(<\[]+", "", u)
    return u


def _detect_tool_request(agent, text: str):
    lower = (text or "").lower()
    prefer: Optional[str] = None
    if "prefer http" in lower or "via http" in lower:
        prefer = "http"
    elif "prefer process" in lower or "via process" in lower or "via stdio" in lower:
        prefer = "process"
    elif "prefer local" in lower:
        prefer = "local"

    # URL detection -> fetch
    url_match = re.search(r"(https?://[^\s]+)", text or "")
    if url_match and _agent_supports_tool(agent, "fetch"):
        raw_url = url_match.group(1)
        args = {"url": _sanitize_url(raw_url)}
        if prefer:
            args["prefer"] = prefer
        return ("fetch", args)

    # Search intent -> web_search
    search_triggers = [
        "search",
        "find",
        "look up",
        "lookup",
        "google",
        "bing",
        "duckduckgo",
        "wikipedia",
        "wiki",
        "who is",
        "what is",
    ]
    if any(t in lower for t in search_triggers) and _agent_supports_tool(agent, "web_search"):
        args = {"query": text}
        top_match = re.search(r"\btop\s+(\d+)", lower)
        if top_match:
            try:
                args["top_n"] = int(top_match.group(1))
            except Exception:
                pass
        if prefer:
            args["prefer"] = prefer
        return ("web_search", args)

    return None


def invoke_agent(
    agent_id: str,
    input_text: str,
    session_id: Optional[str] = None,
    language: Optional[str] = None,
) -> dict:
    """Minimal agent invocation for US2 & US4.
    - Looks up agent by id
    - Creates/continues a session
    - Chooses localized prompt based on Accept-Language (fallback to 'en')
    - Returns a simple echoed output with localized prefix
    - If the agent declares tools (or MCP servers with tools), auto-selects a tool
      when the input expresses a clear intent (URL -> fetch; search-like -> web_search)
    """
    # Load registry from configured directory to find the agent
    registry = AgentRegistry()
    registry.reload()
    agent = registry.get_agent(agent_id)
    if not agent:
        raise KeyError(f"Agent '{agent_id}' not found")

    # Create/continue session
    if session_id:
        session = session_service.continue_session(session_id) or session_service.create_session(
            agent_id
        )
    else:
        session = session_service.create_session(agent_id)

    # Select localized prompt
    selected_lang, prompt_text = get_localized_prompt(agent.prompts or {}, language)

    tool_used: Optional[str] = None
    tool_result: Optional[dict] = None

    # Auto tool routing based on input intent and agent capabilities
    selection = _detect_tool_request(agent, input_text)
    output: str
    if selection:
        tool_name, args = selection
        try:
            service = ToolService()
            tool_result = service.invoke(agent.agent_id, tool_name, args)
            tool_used = tool_name
            # Build a human-readable summary for output
            if tool_name == "web_search":
                results = tool_result.get("results") if isinstance(tool_result, dict) else None
                if isinstance(results, list) and results:
                    lines = []
                    for i, item in enumerate(results[:5], start=1):
                        title = (item or {}).get("title") or (item or {}).get("name") or "Result"
                        url = (item or {}).get("url") or (item or {}).get("link") or ""
                        lines.append(f"{i}. {title} - {url}".strip())
                    output = f"[{agent.agent_id}] web_search results:\n" + "\n".join(lines)
                else:
                    # Fallback summary
                    output = f"[{agent.agent_id}] web_search: {tool_result}"
            elif tool_name == "fetch":
                res_list = tool_result.get("results") if isinstance(tool_result, dict) else None
                r0 = res_list[0] if isinstance(res_list, list) and res_list else {}
                status = r0.get("status") or r0.get("status_code") or r0.get("code")
                body = r0.get("body")
                length = (
                    len(body)
                    if isinstance(body, (str, bytes))
                    else (len(str(body)) if body is not None else 0)
                )
                url_val = args.get("url", "")
                output = f"[{agent.agent_id}] fetch: {url_val} (status={status}, bytes={length})"
            else:
                output = f"[{agent.agent_id}] Tool '{tool_name}' executed."
        except ToolNotFoundError:
            # Graceful fallback to echo if tool not available
            output = compute_output(agent.agent_id, input_text, selected_lang, prompt_text)
        except Exception:
            # Any unexpected error -> echo behavior
            output = compute_output(agent.agent_id, input_text, selected_lang, prompt_text)
    else:
        # No tool intent -> default echo
        output = compute_output(agent.agent_id, input_text, selected_lang, prompt_text)

    # Update session history with language-aware content
    session.history.append(
        {"role": "user", "content": input_text, "language": language or selected_lang}
    )
    session.history.append({"role": "agent", "content": output, "language": selected_lang})

    # Persist minimal history update
    session_service._persist(session)

    resp = {
        "agent_id": agent.agent_id,
        "session_id": session.session_id,
        "output": output,
        "selected_language": selected_lang,
    }
    if tool_used:
        resp["tool_used"] = tool_used
    if tool_result is not None:
        resp["tool_result"] = tool_result
    return resp


# EOF
