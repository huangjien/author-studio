import json
import logging
import os
import select
import subprocess
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    pass


class MCPClient:
    """
    Minimal MCP stdio client using JSON-RPC 2.0 framed with LSP-style headers.

    This client:
    - Spawns a subprocess for the MCP server (e.g., `uvx mcp-server-fetch`)
    - Speaks JSON-RPC over stdin/stdout with `Content-Length` framing
    - Provides `initialize`, `list_tools`, and `call_tool` helpers

    It is intentionally conservative and will fallback in the caller if any
    protocol or transport errors occur.
    """

    def __init__(
        self,
        command: str,
        args: Optional[list[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.proc: Optional[subprocess.Popen] = None
        self._next_id = 1

    def start(self) -> None:
        if self.proc is not None:
            return
        env = os.environ.copy()
        env.update(self.env)
        try:
            self.proc = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
        except Exception as e:  # noqa: BLE001
            raise MCPClientError(f"Failed to start MCP server: {e}")

    def stop(self) -> None:
        proc = self.proc
        self.proc = None
        if not proc:
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except Exception:  # noqa: BLE001
                proc.kill()
        except Exception:  # noqa: BLE001
            pass

    def _write_message(self, payload: Dict[str, Any]) -> None:
        if not self.proc or not self.proc.stdin:
            raise MCPClientError("Process stdin not available")
        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        try:
            self.proc.stdin.write(header)
            self.proc.stdin.write(body)
            self.proc.stdin.flush()
        except Exception as e:  # noqa: BLE001
            raise MCPClientError(f"Failed to write MCP message: {e}")

    def _read_exact(self, n: int, timeout: float) -> bytes:
        if not self.proc or not self.proc.stdout:
            raise MCPClientError("Process stdout not available")
        deadline = time.time() + timeout
        buf = b""
        while len(buf) < n:
            remaining = max(0.0, deadline - time.time())
            if remaining == 0.0:
                raise MCPClientError("Timeout reading MCP body")
            rlist, _, _ = select.select([self.proc.stdout], [], [], remaining)
            if not rlist:
                continue
            chunk = self.proc.stdout.read(n - len(buf))
            if not chunk:
                raise MCPClientError("EOF while reading MCP body")
            buf += chunk
        return buf

    def _readline(self, timeout: float) -> bytes:
        if not self.proc or not self.proc.stdout:
            raise MCPClientError("Process stdout not available")
        deadline = time.time() + timeout
        line = b""
        while True:
            remaining = max(0.0, deadline - time.time())
            if remaining == 0.0:
                raise MCPClientError("Timeout reading MCP header line")
            rlist, _, _ = select.select([self.proc.stdout], [], [], remaining)
            if not rlist:
                continue
            ch = self.proc.stdout.read(1)
            if not ch:
                raise MCPClientError("EOF while reading MCP header line")
            line += ch
            if line.endswith(b"\n"):
                return line

    def _read_message(self, timeout: float = 3.0) -> Dict[str, Any]:
        length: Optional[int] = None
        while True:
            line = self._readline(timeout)
            s = line.decode("ascii", errors="ignore").strip()
            if s == "":
                break
            if s.lower().startswith("content-length:"):
                try:
                    length = int(s.split(":", 1)[1].strip())
                except Exception:  # noqa: BLE001
                    raise MCPClientError("Invalid Content-Length header")
        if length is None:
            raise MCPClientError("Missing Content-Length header")
        body = self._read_exact(length, timeout)
        try:
            return json.loads(body.decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            raise MCPClientError(f"Invalid JSON body: {e}")

    def _request(
        self,
        method: str,
        params: Dict[str, Any],
        timeout: float = 3.0,
    ) -> Dict[str, Any]:
        msg_id = self._next_id
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
            "params": params,
        }
        self._write_message(payload)
        resp = self._read_message(timeout=timeout)
        if resp.get("id") != msg_id:
            raise MCPClientError("Mismatched response id")
        if "error" in resp:
            raise MCPClientError(f"MCP error: {resp['error']}")
        result = resp.get("result")
        if result is None:
            raise MCPClientError("Missing result in MCP response")
        return result

    def initialize(self, timeout: float = 3.0) -> None:
        try:
            self._request(
                "initialize",
                {
                    "capabilities": {},
                    "clientInfo": {"name": "author-studio", "version": "0.1"},
                },
                timeout=timeout,
            )
        except MCPClientError as e:
            logger.debug("MCP initialize ignored/failed: %s", e)

    def list_tools(self, timeout: float = 3.0) -> Dict[str, Any]:
        try:
            return self._request("tools/list", {}, timeout=timeout)
        except MCPClientError as e:
            logger.debug("MCP tools/list failed: %s", e)
            return {}

    def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        timeout: float = 5.0,
    ) -> Dict[str, Any]:
        try:
            return self._request(
                "tools/call",
                {"name": name, "arguments": arguments},
                timeout=timeout,
            )
        except MCPClientError as e:
            logger.debug("MCP tools/call failed: %s", e)
        try:
            return self._request(
                "tools/invoke",
                {"name": name, "arguments": arguments},
                timeout=timeout,
            )
        except MCPClientError as e:
            raise MCPClientError(f"MCP tool invocation failed: {e}")
        # EOF
