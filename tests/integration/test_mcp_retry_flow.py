from fastapi.testclient import TestClient

import src.api.routes.agents as agents_routes
import src.services.mcp_manager as mcp_manager
import src.services.tool_service as tool_service_module
from src.main import app
from src.services.mcp_client import MCPClientError


class FakeAgent:
    def __init__(self, agent_id: str):
        self._agent_id = agent_id

    def model_dump(self) -> dict:
        return {
            "agent_id": self._agent_id,
            "llm_config": {},
            "workflow": {},
            "prompts": {},
            "tools": ["web_search", "fetch"],
            "mcp_servers": [
                {
                    "name": "proc-fetch",
                    "type": "process",
                    "tools": ["web_search", "fetch"],
                    "command": "mcp-server-fetch",
                    "args": [],
                    "env": {},
                    "persistent": True,
                    "initialize_timeout": 0.1,
                    "call_timeout": 1.0,
                    "tool_call_retries": 1,
                    "retry_backoff_ms": 10,
                }
            ],
        }


class FakeRegistry:
    def reload(self, dir_path: str):
        pass

    def get_agent(self, agent_id: str):
        return FakeAgent(agent_id)


class CrashClient:
    def call_tool(self, tool: str, args: dict, timeout: float | None = None):
        # Simulate server crash during first call
        raise MCPClientError("simulated crash")


class OKClient:
    def call_tool(self, tool: str, args: dict, timeout: float | None = None):
        # Simulate successful fetch result after restart
        return {"ok": True, "body": "example"}


class CrashThenOKManager:
    def __init__(self):
        self._restarted = False

    def acquire(self, *args, **kwargs):
        # First acquire returns a client that will crash on call
        return CrashClient()

    def restart(self, *args, **kwargs):
        # Restart returns a healthy client
        self._restarted = True
        return OKClient()


client = TestClient(app)


def test_process_mcp_crash_then_retry_success(monkeypatch):
    # Patch registry in the agents route to serve our fake agent
    monkeypatch.setattr(agents_routes.registry, "get_agent", lambda aid: FakeAgent(aid))
    # Patch ToolService to use our fake registry
    monkeypatch.setattr(tool_service_module, "AgentRegistry", lambda: FakeRegistry())
    # Patch the global mcp_client_manager to our crash-then-ok manager
    monkeypatch.setattr(mcp_manager, "mcp_client_manager", CrashThenOKManager())

    resp = client.post(
        "/agents/alpha-bot/tools/fetch",
        json={"arguments": {"url": "http://example.com"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("tool") == "fetch"
    assert data.get("query") == "http://example.com"
    results = data.get("results")
    assert isinstance(results, list) and len(results) == 1
    assert results[0].get("ok") is True
