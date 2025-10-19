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


def test_invoke_route_success(tmp_path):
    api_key = "unit-key"
    os.environ["API_KEY"] = api_key

    client = TestClient(app)
    resp = client.post(
        "/agents/alpha-bot/invoke",
        headers={"X-API-Key": api_key},
        json={"input": "Hello", "session_id": "s1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("agent_id") == "alpha-bot"
    assert isinstance(data.get("output"), str)
    assert "Echo" in data.get("output", "")


def test_invoke_tool_route_removed():
    client = TestClient(app)
    resp = client.post("/agents/alpha-bot/tools/web_search", json={"arguments": {"query": "x"}})
    assert resp.status_code == 404


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
