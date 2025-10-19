import json
import logging
import os
from typing import Any, Dict, List, Optional

from src.services.mcp_client import MCPClient, MCPClientError

logger = logging.getLogger(__name__)


class MCPClientManager:
    """
    Maintains persistent MCPClient instances per server name.

    - Keeps subprocesses alive across tool invocations
    - Lazily starts clients when first acquired
    - Optionally retries tool calls and can restart the process on failure
    """

    def __init__(self) -> None:
        self._clients: Dict[str, MCPClient] = {}
        self._initialized: Dict[str, bool] = {}
        self._servers_config: List[Dict[str, Any]] = []

    def acquire(
        self,
        name: str,
        command: str,
        args: Optional[list[str]] = None,
        env: Optional[Dict[str, str]] = None,
        initialize_timeout: float = 3.0,
    ) -> MCPClient:
        client = self._clients.get(name)
        if client is None:
            client = MCPClient(command=command, args=args or [], env=env or {})
            try:
                client.start()
                try:
                    client.initialize(timeout=initialize_timeout)
                except MCPClientError as e:
                    # Some servers do not require explicit initialize; log and continue
                    logger.debug("MCP initialize skipped/failed for '%s': %s", name, e)
                self._clients[name] = client
                self._initialized[name] = True
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to start MCP client '%s': %s", name, e)
                # Leave it out of the cache on failure
                raise
        return client

    def restart(
        self,
        name: str,
        command: str,
        args: Optional[list[str]] = None,
        env: Optional[Dict[str, str]] = None,
        initialize_timeout: float = 3.0,
    ) -> MCPClient:
        # Stop existing and recreate
        old = self._clients.pop(name, None)
        if old is not None:
            try:
                old.stop()
            except Exception:  # noqa: BLE001
                pass
        self._initialized.pop(name, None)
        return self.acquire(name, command, args, env, initialize_timeout)

    def stop_all(self) -> None:
        for name, client in list(self._clients.items()):
            try:
                client.stop()
            except Exception:  # noqa: BLE001
                pass
        self._clients.clear()
        self._initialized.clear()

    def load_servers_config(self, path: str) -> None:
        """Load MCP servers from a JSON file for status reporting.
        This does not start clients; it only caches configuration metadata.
        """
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._servers_config = data
        except Exception as e:
            # Best-effort; avoid raising on status load
            print(f"[MCPClientManager] Failed to load servers config: {e}")

    def get_status(
        self, ping: bool = False, initialize_timeout: float = 3.0, list_timeout: float = 2.0
    ) -> List[Dict[str, Any]]:
        """Return lightweight status info for configured MCP servers.

        If a persistent process server already has a live client, perform a
        light tools/list ping to assess reachability. If ping=True, perform
        an ephemeral ping for process servers even when no cached client exists.
        """
        status: List[Dict[str, Any]] = []
        for s in self._servers_config:
            name = s.get("name")
            stype = s.get("type")
            tools = s.get("tools") or []
            persistent = bool(s.get("persistent", False))
            reachable: Optional[bool] = None
            reason: Optional[str] = None

            if stype == "process":
                init_to = float(s.get("initialize_timeout", initialize_timeout))
                list_to = float(s.get("list_tools_timeout", list_timeout))
                client = self._clients.get(name) if persistent else None

                if client:
                    try:
                        resp = client.list_tools(timeout=list_to) or {}
                        items = resp.get("tools") if isinstance(resp, dict) else None
                        if isinstance(items, list) and items:
                            reachable = True
                        else:
                            reachable = False
                            reason = "tools/list returned empty result"
                    except Exception as e:
                        reachable = False
                        reason = str(e)[:200]
                elif ping:
                    cmd = s.get("command") or ""
                    args = s.get("args") or []
                    env = s.get("env") or {}
                    try:
                        tmp = MCPClient(command=cmd, args=args, env=env)
                        tmp.start()
                        try:
                            try:
                                tmp.initialize(timeout=init_to)
                            except MCPClientError as e:
                                logger.debug(
                                    "MCP initialize (ephemeral) skipped/failed for '%s': %s",
                                    name,
                                    e,
                                )
                            resp = tmp.list_tools(timeout=list_to) or {}
                            items = resp.get("tools") if isinstance(resp, dict) else None
                            if isinstance(items, list) and items:
                                reachable = True
                            else:
                                reachable = False
                                reason = "tools/list returned empty result"
                        finally:
                            try:
                                tmp.stop()
                            except Exception:
                                pass
                    except Exception as e:
                        reachable = False
                        reason = str(e)[:200]

            status.append(
                {
                    "name": name,
                    "type": stype,
                    "tools": tools,
                    "persistent": persistent,
                    "reachable": reachable,
                    "unreachable_reason": reason,
                }
            )

        return status

    # NEW: Aggregate tools across configured MCP servers
    def list_all_tools(
        self,
        query_live: bool = True,
        initialize_timeout: float = 3.0,
        list_timeout: float = 3.0,
    ) -> List[Dict[str, Any]]:
        """
        Aggregate tools across configured MCP servers.

        If query_live is True, attempt to query process-based servers to retrieve the
        actual tool list; otherwise, use the configured 'tools' field.

        Returns a list of entries:
        [{"name": str, "server": str, "type": str, "reachable": bool|None}]
        """
        results: List[Dict[str, Any]] = []
        for s in self._servers_config:
            name = s.get("name")
            stype = s.get("type")
            tools = s.get("tools") or []
            persistent = bool(s.get("persistent", False))
            reachable = None
            names: List[str] = []

            if query_live and stype == "process":
                cmd = s.get("command") or ""
                args = s.get("args") or []
                env = s.get("env") or {}
                init_to = float(s.get("initialize_timeout", initialize_timeout))
                list_to = float(s.get("list_tools_timeout", list_timeout))
                try:
                    if persistent:
                        client = self.acquire(
                            name=name,
                            command=cmd,
                            args=args,
                            env=env,
                            initialize_timeout=init_to,
                        )
                        resp = client.list_tools(timeout=list_to) or {}
                    else:
                        tmp = MCPClient(command=cmd, args=args, env=env)
                        tmp.start()
                        try:
                            tmp.initialize(timeout=init_to)
                            resp = tmp.list_tools(timeout=list_to) or {}
                        finally:
                            tmp.stop()
                    reachable = bool(resp)
                    items = resp.get("tools") if isinstance(resp, dict) else None
                    if isinstance(items, list) and items:
                        for item in items:
                            nm = (item or {}).get("name") if isinstance(item, dict) else None
                            if isinstance(nm, str) and nm:
                                names.append(nm)
                    else:
                        # Fallback to configured tools if live response is empty or malformed
                        names = tools or []
                except Exception:
                    reachable = False
                    names = tools or []
            else:
                names = tools or []

            for nm in names:
                results.append(
                    {
                        "name": nm,
                        "server": name,
                        "type": stype,
                        "reachable": reachable,
                    }
                )
        return results


# Global singleton manager
mcp_client_manager = MCPClientManager()
