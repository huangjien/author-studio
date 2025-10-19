import importlib
import os

from fastapi.testclient import TestClient

from src.main import app


def test_list_agents_endpoint():
    client = TestClient(app)
    resp = client.get("/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # Should include at least one agent from default configs
    assert any("agent_id" in a for a in data)


def test_get_agent_not_found():
    client = TestClient(app)
    resp = client.get("/agents/unknown-agent")
    assert resp.status_code == 404


def test_list_agent_tools_unknown_agent():
    client = TestClient(app)
    resp = client.get("/agents/unknown-agent/tools")
    assert resp.status_code == 404


def test_list_agent_tools_generic_error(monkeypatch):
    import src.api.routes.agents as routes

    class BoomService:
        def list_tools(self, agent_id):
            raise RuntimeError("boom")

    monkeypatch.setattr(routes, "ToolService", BoomService, raising=True)

    client = TestClient(app)
    # Use a known good agent id from default configs
    resp = client.get("/agents/alpha-bot/tools")
    assert resp.status_code == 500


def test_invoke_route_success(monkeypatch, tmp_path):
    api_key = "unit-key"
    os.environ["API_KEY"] = api_key
    import src.services.agent_service as agent_service_module

    importlib.reload(agent_service_module)

    def ok(**kwargs):
        return {"ok": True, "echo": kwargs["input_text"]}

    monkeypatch.setattr(agent_service_module, "invoke_agent", ok, raising=True)

    client = TestClient(app)
    resp = client.post(
        "/agents/alpha-bot/invoke",
        headers={"X-API-Key": api_key},
        json={"input": "Hello", "session_id": "s1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is True
    assert data.get("echo") == "Hello"


def test_invoke_tool_not_implemented(monkeypatch):
    import src.api.routes.agents as routes

    class StubToolService:
        def invoke(self, agent_id: str, tool_name: str, arguments: dict):
            raise NotImplementedError("not implemented")

    monkeypatch.setattr(routes, "ToolService", StubToolService, raising=True)

    client = TestClient(app)
    resp = client.post("/agents/alpha-bot/tools/web_search", json={"arguments": {"query": "x"}})
    assert resp.status_code == 501


def test_mcp_tool_proxy_success():
    client = TestClient(app)
    resp = client.post(
        "/mcp/tools/web_search",
        json={"arguments": {"query": "hello", "top_n": 1}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tool"] == "web_search"
    assert isinstance(data.get("results"), list)


def test_mcp_tool_proxy_unknown_tool():
    client = TestClient(app)
    resp = client.post(
        "/mcp/tools/unknown",
        json={"arguments": {"query": "hello"}},
    )
    assert resp.status_code == 404


def test_mcp_tool_proxy_generic_error(monkeypatch):

    def bad_web_search(**kwargs):  # signature is flexible
        raise RuntimeError("boom")

    # Patch the provider to raise
    import src.tools.providers.local_web_search as provider

    monkeypatch.setattr(provider, "web_search", bad_web_search, raising=True)

    client = TestClient(app)
    resp = client.post(
        "/mcp/tools/web_search",
        json={"arguments": {"query": "hello", "top_n": 1}},
    )
    assert resp.status_code == 500
