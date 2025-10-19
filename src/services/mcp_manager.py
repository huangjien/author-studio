import logging
from typing import Dict, Optional

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


# Global singleton manager
mcp_client_manager = MCPClientManager()
