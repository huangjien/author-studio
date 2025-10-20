import glob
import logging
import time
from typing import Any, Dict, Optional

import yaml

from src.agents.registry import AgentRegistry
from src.config.env import settings

logger = logging.getLogger(__name__)


class ToolNotFoundError(Exception):
    pass


class ToolService:
    """Resolves and invokes tools declared on agents via MCP servers.

    Supported server types:
    - local: tools implemented in this repository (deterministic, offline)
    - http: future support for remote MCP servers over HTTP (not implemented yet)
    - process: configured MCP servers launched as subprocesses (temporary bridge)
    """

    def __init__(self, dir_path: Optional[str] = None) -> None:
        self._registry = AgentRegistry()
        # Track the directory to reload from
        self._dir_path = dir_path or settings.agent_config_dir
        self._registry.reload(dir_path=self._dir_path)

    def reload(self, dir_path: str | None = None) -> None:
        # If a dir path is passed, prefer it; otherwise keep existing
        if dir_path is not None:
            self._dir_path = dir_path
        self._registry.reload(dir_path=self._dir_path)

    def _resolve_server(self, agent: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
        # Prefer explicit MCP servers if configured
        for server in agent.get("mcp_servers", []) or []:
            tools = server.get("tools", []) or []
            if tool_name in tools:
                return server
        # Default allow local web_search for convenience in demos/tests
        if tool_name == "web_search":
            return {"name": "default-local", "type": "local", "tools": [tool_name]}
        # Graceful fallback: if agent declares the tool but no servers are configured,
        # default to a local provider to keep examples working.
        if tool_name in (agent.get("tools") or []):
            return {"name": "default-local", "type": "local", "tools": [tool_name]}
        raise ToolNotFoundError(f"Tool '{tool_name}' not found for agent '{agent.get('agent_id')}'")

    def _resolve_servers(
        self,
        agent: Dict[str, Any],
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> list[Dict[str, Any]]:
        """Return an ordered list of candidate MCP servers for the tool.

        Heuristics:
        - Prefer process/http servers for internet-backed tools like web_search.
        - Prefer process for fetch.
        - Honor optional 'priority' field: high > medium > low.
        - Prefer persistent process clients.
        - Allow caller hint via arguments['prefer'] in {'process','http','local','stdio'}.
        - Fallback to local provider when appropriate.
        """
        candidates: list[Dict[str, Any]] = []
        for server in agent.get("mcp_servers", []) or []:
            tools = server.get("tools", []) or []
            if tool_name in tools:
                candidates.append(server)

        # If no candidates, consider local fallback when tool is declared or is web_search
        fallback_local = {"name": "default-local", "type": "local", "tools": [tool_name]}
        if not candidates:
            if tool_name == "web_search" or tool_name in (agent.get("tools") or []):
                candidates = [fallback_local]
            else:
                return []

        def _score(server: Dict[str, Any]) -> int:
            s = 0
            st = server.get("type")
            # Base preference by tool type
            if tool_name == "web_search":
                s += 30 if st == "process" else 20 if st == "http" else 10 if st == "local" else 0
            elif tool_name == "fetch":
                s += 30 if st == "process" else 20 if st == "http" else 0
            else:
                s += 20 if st == "process" else 10 if st == "http" else 5 if st == "local" else 0
            # Persistent clients slightly preferred
            if st == "process" and bool(server.get("persistent", True)):
                s += 5
            # Honor optional priority
            pr = server.get("priority")
            if pr == "high":
                s += 10
            elif pr == "low":
                s -= 10
            # Caller preference hint
            prefer = (arguments or {}).get("prefer")
            if prefer in ("process", "stdio"):
                s += 5 if st == "process" else -5
            elif prefer == "http":
                s += 5 if st == "http" else -5
            elif prefer == "local":
                s += 5 if st == "local" else -5
            # Simple content hint for web_search
            q = (arguments or {}).get("query") or (arguments or {}).get("q") or ""
            if isinstance(q, str) and "wikipedia" in q.lower():
                s += 3 if st == "process" else 0
            return s

        # Stable sort by score, then by original order
        indexed = list(enumerate(candidates))
        indexed.sort(key=lambda tup: (_score(tup[1]), -tup[0]), reverse=True)
        ordered = [srv for _, srv in indexed]
        return ordered

    def _fallback_agent_from_yaml(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to load a minimal agent dict directly from YAML files if the
        validated registry did not include it (e.g., missing 'prompts').
        """
        patterns = [f"{self._dir_path}/*.yaml", f"{self._dir_path}/*.yml"]
        for pattern in patterns:
            for path in glob.glob(pattern):
                try:
                    with open(path, "r") as f:
                        data = yaml.safe_load(f) or {}
                except Exception:
                    continue
                name = str(data.get("name", "")).strip()
                slug = (
                    name.lower().replace(" ", "-").replace("_", "-").replace("--", "-").strip("-")
                )
                if slug == agent_id:
                    return {
                        "agent_id": agent_id,
                        "llm": data.get("llm", {}),
                        "workflow": data.get("workflow", {}),
                        "prompts": data.get("prompts") or {},
                        "tools": data.get("tools") or [],
                        "mcp_servers": data.get("mcp_servers") or [],
                    }
        return None

    def _collect_mcp_servers_from_yaml(self, agent_id: str) -> list[Dict[str, Any]]:
        """Aggregate mcp_servers for a given agent_id across all YAML files.

        This is robust to duplicate agent files by unioning declared mcp servers.
        """
        patterns = [f"{self._dir_path}/*.yaml", f"{self._dir_path}/*.yml"]
        servers: list[Dict[str, Any]] = []
        for pattern in patterns:
            for path in glob.glob(pattern):
                try:
                    with open(path, "r") as f:
                        data = yaml.safe_load(f) or {}
                except Exception:
                    continue
                name = str(data.get("name", "")).strip()
                slug = (
                    name.lower().replace(" ", "-").replace("_", "-").replace("--", "-").strip("-")
                )
                if slug == agent_id:
                    for s in data.get("mcp_servers") or []:
                        if isinstance(s, dict) and s:
                            servers.append(s)
        return servers

    def list_tools(self, agent_id: str) -> Dict[str, Any]:
        """List available tools for an agent.

        Attempts to query MCP servers for declared tools. For process-based servers:
        - If persistent=True, uses the persistent MCP client manager to call list_tools.
        - If persistent=False, starts a temporary client, calls list_tools, then stops.
        For HTTP servers, returns the configured 'tools' list (no remote list supported yet).
        For local servers, returns the configured 'tools' list, or ['web_search'] if none.
        """
        self._registry.reload(dir_path=self._dir_path)
        agent_obj = self._registry.get_agent(agent_id)
        agent_dict: Optional[Dict[str, Any]] = None
        if agent_obj:
            agent_dict = agent_obj.model_dump()
        else:
            agent_dict = self._fallback_agent_from_yaml(agent_id)
        if not agent_dict:
            raise KeyError(f"Agent '{agent_id}' not found")

        listed: set[str] = set()
        servers = agent_dict.get("mcp_servers", []) or []
        # If registry-provided agent lacks mcp_servers, fallback to YAML-defined ones
        if not servers:
            servers = self._collect_mcp_servers_from_yaml(agent_id) or []
        # Helper to add tools safely

        def add_tools(tools: list[str] | None):
            for t in tools or []:
                if isinstance(t, str) and t:
                    listed.add(t)

        for server in servers:
            server_type = server.get("type")
            server_tools = server.get("tools", []) or []
            if server_type == "local":
                # Local providers: rely on configured tools; default web_search
                add_tools(server_tools or ["web_search"])
            elif server_type == "http":
                # HTTP servers: return configured list for now
                add_tools(server_tools)
            elif server_type == "process":
                # Process servers: try querying the MCP server; fallback to configured list
                init_timeout = float(server.get("initialize_timeout", 3.0))
                list_timeout = float(server.get("list_tools_timeout", 3.0))
                cmd = server.get("command") or ""
                args = server.get("args") or []
                env = server.get("env") or {}
                persistent = bool(server.get("persistent", True))
                try:
                    if persistent:
                        from src.services.mcp_manager import mcp_client_manager

                        client = mcp_client_manager.acquire(
                            name=server.get("name", "process"),
                            command=cmd,
                            args=args,
                            env=env,
                            initialize_timeout=init_timeout,
                        )
                        resp = client.list_tools(timeout=list_timeout) or {}
                    else:
                        from src.services.mcp_client import MCPClient

                        client = MCPClient(command=cmd, args=args, env=env)
                        client.start()
                        try:
                            client.initialize(timeout=init_timeout)
                            resp = client.list_tools(timeout=list_timeout) or {}
                        finally:
                            client.stop()
                    # Normalize response shape to names
                    names: list[str] = []
                    tools_payload = resp.get("tools") if isinstance(resp, dict) else None
                    if isinstance(tools_payload, list):
                        for item in tools_payload:
                            name = (item or {}).get("name") if isinstance(item, dict) else None
                            if isinstance(name, str) and name:
                                names.append(name)
                    add_tools(names or server_tools)
                except Exception:
                    add_tools(server_tools)
            else:
                # Unknown server type; ignore
                continue
        # Also include agent-level tools that may be provided locally
        add_tools(agent_dict.get("tools") or [])
        return {"tools": sorted(list(listed))}

    def _invoke_on_server(
        self,
        server: Dict[str, Any],
        agent_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Invoke a tool on a specific server, without performing cross-server fallback.

        Raises ToolNotFoundError if the server fails or the tool is not implemented.
        """
        server_type = server.get("type")
        if server_type == "local":
            if tool_name == "web_search":
                from src.tools.providers.local_web_search import web_search

                query = arguments.get("query") or arguments.get("q") or ""
                top_n = int(arguments.get("top_n", 5))
                return web_search(query=query, top_n=top_n)
            if tool_name == "fetch":
                from src.tools.providers.local_fetch import fetch as local_fetch

                url = arguments.get("url") or ""
                return local_fetch(url=url, timeout=float(arguments.get("timeout", 5.0)))
            raise ToolNotFoundError(f"Local tool '{tool_name}' not implemented")
        elif server_type == "http":
            base_url = server.get("url")
            if not base_url:
                raise ToolNotFoundError("HTTP MCP server missing 'url'")
            headers = server.get("headers") or {}
            path_template = server.get("path_template") or "/tools/{tool_name}/invoke"
            try:
                path = path_template.format(agent_id=agent_id, tool_name=tool_name)
            except Exception:  # noqa: BLE001
                path = f"/tools/{tool_name}/invoke"
            url = f"{base_url.rstrip('/')}{path}"
            try:
                import requests

                resp = requests.post(url, json={"arguments": arguments}, headers=headers, timeout=5)
                if resp.status_code >= 400:
                    logger.warning(
                        "HTTP MCP server returned status %s for %s", resp.status_code, url
                    )
                    raise ToolNotFoundError(f"HTTP MCP server error (status {resp.status_code})")
                return resp.json()
            except Exception as e:  # noqa: BLE001
                logger.error("HTTP MCP server request failed: %s", e)
                raise ToolNotFoundError(f"HTTP MCP server error: {e}")
        elif server_type == "process":
            try:
                cmd = server.get("command") or ""
                args = server.get("args") or []
                env = server.get("env") or {}
                persistent = bool(server.get("persistent", True))
                init_timeout = float(server.get("initialize_timeout", 3.0))
                call_timeout = float(server.get("call_timeout", 5.0))
                retries = int(server.get("tool_call_retries", 1))
                backoff_ms = int(server.get("retry_backoff_ms", 250))

                if persistent:
                    from src.services.mcp_client import MCPClientError
                    from src.services.mcp_manager import mcp_client_manager

                    client = mcp_client_manager.acquire(
                        name=server.get("name", "process"),
                        command=cmd,
                        args=args,
                        env=env,
                        initialize_timeout=init_timeout,
                    )

                    def _call_with_retry(tool: str, args_dict: Dict[str, Any]) -> Dict[str, Any]:
                        attempts = max(1, retries + 1)
                        last_err: Exception | None = None
                        current_client = client
                        for i in range(attempts):
                            try:
                                return current_client.call_tool(
                                    tool,
                                    args_dict,
                                    timeout=call_timeout,
                                )
                            except MCPClientError as e:
                                last_err = e
                                logger.warning(
                                    "MCP call failed (attempt %s/%s) " "for tool '%s': %s",
                                    i + 1,
                                    attempts,
                                    tool,
                                    e,
                                )
                                # On retry, restart the client to recover from server crash
                                try:
                                    current_client = mcp_client_manager.restart(
                                        name=server.get("name", "process"),
                                        command=cmd,
                                        args=args,
                                        env=env,
                                        initialize_timeout=init_timeout,
                                    )
                                except Exception as restart_err:  # noqa: BLE001
                                    last_err = restart_err
                                    break
                                time.sleep(max(0, backoff_ms) / 1000.0)
                        raise ToolNotFoundError(
                            f"Process MCP server error for tool '{tool}': {last_err}"
                        )

                    if tool_name == "fetch":
                        result = _call_with_retry("fetch", arguments)
                        return {
                            "tool": "fetch",
                            "query": arguments.get("url", ""),
                            "results": [result],
                        }
                    if tool_name == "web_search":
                        q = arguments.get("query") or arguments.get("q") or ""
                        top_n = int(arguments.get("top_n", 5))
                        url = (
                            "https://en.wikipedia.org/w/api.php"
                            "?action=query&list=search&format=json&"
                            f"srlimit={max(1, min(top_n, 5))}&srsearch={q}"
                        )
                        fetch_res = _call_with_retry("fetch", {"url": url})
                        if not isinstance(fetch_res, dict):
                            fetch_res = {}
                        data = fetch_res.get("body")
                        try:
                            import json as _json

                            parsed = _json.loads(data) if isinstance(data, (str, bytes)) else data
                        except Exception:  # noqa: BLE001
                            parsed = {}
                        results = []
                        for item in (parsed.get("query", {}).get("search", []) or [])[:top_n]:
                            title = item.get("title") or ""
                            snippet = item.get("snippet") or ""
                            article_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                            results.append(
                                {
                                    "title": title,
                                    "url": article_url,
                                    "snippet": snippet,
                                }
                            )
                        return {"tool": "web_search", "query": q, "results": results}
                    raise ToolNotFoundError(f"Process-based tool '{tool_name}' not implemented")
                else:
                    # Ephemeral process behaviour (legacy): start per call, stop after
                    from src.services.mcp_client import MCPClient, MCPClientError

                    client = MCPClient(command=cmd, args=args, env=env)
                    client.start()
                    try:
                        client.initialize(timeout=init_timeout)

                        def _call_ephemeral(tool: str, args_dict: Dict[str, Any]) -> Dict[str, Any]:
                            attempts = max(1, retries + 1)
                            last_err: Exception | None = None
                            for i in range(attempts):
                                try:
                                    return client.call_tool(
                                        tool,
                                        args_dict,
                                        timeout=call_timeout,
                                    )
                                except MCPClientError as e:
                                    last_err = e
                                    logger.warning(
                                        "Ephemeral MCP call failed (attempt %s/%s) "
                                        "for tool '%s': %s",
                                        i + 1,
                                        attempts,
                                        tool,
                                        e,
                                    )
                                    time.sleep(max(0, backoff_ms) / 1000.0)
                            raise ToolNotFoundError(
                                f"Process MCP server error for tool '{tool}': {last_err}"
                            )

                        if tool_name == "fetch":
                            result = _call_ephemeral("fetch", arguments)
                            return {
                                "tool": "fetch",
                                "query": arguments.get("url", ""),
                                "results": [result],
                            }
                        if tool_name == "web_search":
                            q = arguments.get("query") or arguments.get("q") or ""
                            top_n = int(arguments.get("top_n", 5))
                            url = (
                                "https://en.wikipedia.org/w/api.php"
                                "?action=query&list=search&format=json&"
                                f"srlimit={max(1, min(top_n, 5))}&srsearch={q}"
                            )
                            fetch_res = _call_ephemeral("fetch", {"url": url})
                            if not isinstance(fetch_res, dict):
                                fetch_res = {}
                            data = fetch_res.get("body")
                            try:
                                import json as _json

                                parsed = (
                                    _json.loads(data) if isinstance(data, (str, bytes)) else data
                                )
                            except Exception:  # noqa: BLE001
                                parsed = {}
                            results = []
                            for item in (parsed.get("query", {}).get("search", []) or [])[:top_n]:
                                title = item.get("title") or ""
                                snippet = item.get("snippet") or ""
                                article_url = (
                                    "https://en.wikipedia.org/wiki/" f"{title.replace(' ', '_')}"
                                )
                                results.append(
                                    {
                                        "title": title,
                                        "url": article_url,
                                        "snippet": snippet,
                                    }
                                )
                            return {"tool": "web_search", "query": q, "results": results}
                        raise ToolNotFoundError(f"Process-based tool '{tool_name}' not implemented")
                    finally:
                        client.stop()
            except Exception as e:  # noqa: BLE001
                logger.warning("MCP stdio client failed: %s", e)
                raise ToolNotFoundError(f"Process MCP server error for tool '{tool_name}': {e}")
        else:
            raise ToolNotFoundError(f"Unsupported MCP server type '{server_type}'")

    def invoke(
        self,
        agent_id: str,
        tool_name: str,
        arguments: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        # Ensure registry reflects current configuration at invocation time
        self._registry.reload(dir_path=self._dir_path)
        agent_obj = self._registry.get_agent(agent_id)
        agent_dict: Optional[Dict[str, Any]] = None
        if agent_obj:
            agent_dict = agent_obj.model_dump()
        else:
            agent_dict = self._fallback_agent_from_yaml(agent_id)
        if not agent_dict:
            raise KeyError(f"Agent '{agent_id}' not found")

        arguments = arguments or {}

        # Auto-select candidate servers and try them in order
        candidates = self._resolve_servers(agent_dict, tool_name, arguments)
        if not candidates:
            # Final graceful fallback for demos/tests with consistent metadata
            if tool_name == "web_search":
                from src.tools.providers.local_web_search import web_search

                query = arguments.get("query") or arguments.get("q") or ""
                top_n = int(arguments.get("top_n", 5))
                return web_search(query=query, top_n=top_n)
            if tool_name == "fetch":
                from src.tools.providers.local_fetch import fetch as local_fetch

                url = arguments.get("url") or ""
                return local_fetch(url=url, timeout=float(arguments.get("timeout", 5.0)))
            raise ToolNotFoundError(f"Tool '{tool_name}' not found for agent '{agent_id}'")

        errors: list[str] = []
        for server in candidates:
            try:
                data = self._invoke_on_server(server, agent_id, tool_name, arguments)
                return {
                    "provider": server.get("type"),
                    "server": server.get("name"),
                    "data": data,
                }
            except ToolNotFoundError as e:
                # Try next candidate
                logger.info(
                    "Server '%s' (%s) failed for tool '%s': %s",
                    server.get("name"),
                    server.get("type"),
                    tool_name,
                    e,
                )
                errors.append(str(e))
                continue

        # If all candidates failed, last resort local fallback for web_search
        if tool_name == "web_search":
            from src.tools.providers.local_web_search import web_search

            query = arguments.get("query") or arguments.get("q") or ""
            top_n = int(arguments.get("top_n", 5))
            return {
                "provider": "local",
                "server": "default-local",
                "data": web_search(query=query, top_n=top_n),
            }
        if tool_name == "fetch":
            from src.tools.providers.local_fetch import fetch as local_fetch

            url = arguments.get("url") or ""
            return {
                "provider": "local",
                "server": "default-local",
                "data": local_fetch(url=url, timeout=float(arguments.get("timeout", 5.0))),
            }

        raise ToolNotFoundError(
            f"No MCP server succeeded for tool '{tool_name}'. Errors: {'; '.join(errors)}"
        )


tool_service = ToolService()
