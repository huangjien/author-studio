from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_list_agent_tools_alpha_bot():
    resp = client.get("/agents/alpha-bot/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    tools = data.get("tools")
    assert isinstance(tools, list)
    # Alpha Bot declares web_search and fetch in YAML under process server
    assert "web_search" in tools
    assert "fetch" in tools
