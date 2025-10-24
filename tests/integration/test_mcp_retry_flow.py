from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_mcp_proxy_web_search_success():
    resp = client.post(
        "/mcp/tools/web_search",
        json={"arguments": {"query": "hello", "top_n": 1}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tool"] == "web_search"
    assert isinstance(data.get("results"), list)


def test_mcp_proxy_unknown_tool_404():
    resp = client.post(
        "/mcp/tools/fetch",
        json={"arguments": {"url": "http://example.com"}},
    )
    assert resp.status_code == 404