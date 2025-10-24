from typing import Any

import src.services.mcp_manager as mcp_manager
from src.services.tool_service import ToolService


class FakeAgent:
    def __init__(self, agent_id: str, mcp_servers: list[dict[str, Any]]):
        self._agent_id = agent_id
        self._mcp_servers = mcp_servers

    def model_dump(self) -> dict[str, Any]:
        return {
            "agent_id": self._agent_id,
            "llm_config": {},
            "workflow": {},
            "prompts": {},
            "tools": ["web_search", "fetch"],
            "mcp_servers": self._mcp_servers,
        }


def test_tool_service_process_fallback_to_local(monkeypatch):
    # Simulate manager failure to force fallback
    class FailMgr:
        def acquire(self, *args, **kwargs):
            raise Exception("boom")

    monkeypatch.setattr(mcp_manager, "mcp_client_manager", FailMgr())

    ts = ToolService(dir_path="agent_configs")

    fake_agent = FakeAgent(
        agent_id="alpha",
        mcp_servers=[
            {
                "name": "proc-fetch",
                "type": "process",
                "tools": ["web_search", "fetch"],
                "command": "mcp-server-fetch",
                "persistent": True,
            }
        ],
    )

    # Patch registry to return our fake agent
    monkeypatch.setattr(ts._registry, "get_agent", lambda aid: fake_agent)

    res = ts.invoke("alpha", "web_search", {"query": "Python", "top_n": 1})
    assert isinstance(res, dict)
    assert res.get("provider") == "local"
    assert res.get("server") == "default-local"
    assert isinstance(res.get("data"), dict)
    payload = res["data"]
    assert payload.get("tool") == "web_search"
    assert "results" in payload


def test_tool_service_process_fetch_success(monkeypatch):
    # Stub manager to return a fake persistent client
    class FakeClient:
        def call_tool(self, name, args_dict, timeout=5.0):
            assert name == "fetch"
            # minimal fields used by ToolService to construct result
            return {"status": 200, "body": "ok", "headers": {}, "url": args_dict.get("url", "")}

    class FakeMgr:
        def acquire(self, *args, **kwargs):
            return FakeClient()

        def restart(self, *args, **kwargs):
            return FakeClient()

    monkeypatch.setattr(mcp_manager, "mcp_client_manager", FakeMgr())

    ts = ToolService(dir_path="agent_configs")

    fake_agent = FakeAgent(
        agent_id="alpha",
        mcp_servers=[
            {
                "name": "proc-fetch",
                "type": "process",
                "tools": ["web_search", "fetch"],
                "command": "mcp-server-fetch",
                "persistent": True,
            }
        ],
    )

    monkeypatch.setattr(ts._registry, "get_agent", lambda aid: fake_agent)

    res = ts.invoke("alpha", "fetch", {"url": "https://example.com"})
    assert isinstance(res, dict)
    assert res.get("provider") == "process"
    assert res.get("server") == "proc-fetch"
    assert isinstance(res.get("data"), dict)
    payload = res["data"]
    assert payload.get("tool") == "fetch"
    assert isinstance(payload.get("results"), list)
    assert payload["results"][0]["status"] == 200