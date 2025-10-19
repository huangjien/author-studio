from typing import Any, Dict

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_invoke_tool_web_search_success() -> None:
    payload: Dict[str, Any] = {"arguments": {"query": "python", "top_n": 1}}
    resp = client.post("/agents/alpha-bot/tools/web_search", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tool"] == "web_search"
    assert data["query"] == "python"
    assert isinstance(data["results"], list)


def test_invoke_tool_not_found() -> None:
    payload: Dict[str, Any] = {"arguments": {"query": "python", "top_n": 1}}
    resp = client.post("/agents/alpha-bot/tools/unknown_tool", json=payload)
    assert resp.status_code == 404


def test_agent_not_found_for_tool_invocation() -> None:
    payload: Dict[str, Any] = {"arguments": {"query": "python", "top_n": 1}}
    resp = client.post("/agents/unknown-agent/tools/web_search", json=payload)
    assert resp.status_code == 404
