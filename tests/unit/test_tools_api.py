from typing import Any, Dict

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_mcp_web_search_success() -> None:
    payload: Dict[str, Any] = {"arguments": {"query": "python", "top_n": 1}}
    resp = client.post("/mcp/tools/web_search", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tool"] == "web_search"
    assert data["query"] == "python"
    assert isinstance(data["results"], list)


def test_mcp_tool_not_found() -> None:
    payload: Dict[str, Any] = {"arguments": {"query": "python", "top_n": 1}}
    resp = client.post("/mcp/tools/unknown_tool", json=payload)
    assert resp.status_code == 404