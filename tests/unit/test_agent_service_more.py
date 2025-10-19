import os
import shutil
import tempfile
from types import SimpleNamespace

import src.services.agent_service as agent_service
from src.services.tool_service import ToolNotFoundError


def make_temp_agent_dir(yaml_payload: dict) -> str:
    temp_dir = tempfile.mkdtemp(prefix="agent_cfg_")
    cfg_path = os.path.join(temp_dir, "alpha.yaml")
    import yaml

    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(yaml_payload, f, sort_keys=False)
    return temp_dir


def teardown_env(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


class FakeToolService:
    def __init__(self, dir_path=None):
        pass

    def list_tools(self, agent_id):  # noqa: A003
        return {"agent_id": agent_id, "tools": ["web_search", "fetch", "bad", "explode"]}

    def invoke(self, agent_id, tool, arguments):
        if tool == "web_search":
            top_n = arguments.get("top_n", 3)
            results = [{"title": "Py", "url": "http://py", "snippet": "..."} for _ in range(top_n)]
            return {"tool": "web_search", "query": arguments.get("query", ""), "results": results}
        if tool == "fetch":
            payload = {
                "tool": "fetch",
                "query": arguments.get("url", ""),
                "results": [
                    {
                        "status": 200,
                        "body": "data",
                        "headers": {},
                        "url": arguments.get("url", ""),
                        "content_type": "text/plain",
                    }
                ],
            }
            return payload
        if tool == "bad":
            raise ToolNotFoundError("bad tool")
        raise RuntimeError("boom")


def test_agent_supports_tool_aggregated_list(monkeypatch):
    monkeypatch.setattr(agent_service, "ToolService", FakeToolService)
    agent = SimpleNamespace(agent_id="alpha-bot", tools=[], mcp_servers=None)
    assert agent_service._agent_supports_tool(agent, "fetch") is True
    assert agent_service._agent_supports_tool(agent, "web_search") is True


def test_invoke_agent_web_search_formatting(monkeypatch):
    temp_dir = make_temp_agent_dir({"name": "Alpha Bot", "tools": ["web_search"]})
    try:
        os.environ["AGENT_CONFIG_DIR"] = temp_dir
        monkeypatch.setattr(agent_service, "ToolService", FakeToolService)
        out = agent_service.invoke_agent("alpha-bot", "Search top 2 Python topics", None)
        assert out["tool_used"] == "web_search"
        # Expect enumerated lines in output
        assert "1." in out["output"] and "2." in out["output"]
    finally:
        teardown_env(temp_dir)
        os.environ.pop("AGENT_CONFIG_DIR", None)


def test_invoke_agent_fetch_formatting(monkeypatch):
    temp_dir = make_temp_agent_dir({"name": "Alpha Bot", "tools": ["fetch"]})
    try:
        os.environ["AGENT_CONFIG_DIR"] = temp_dir
        monkeypatch.setattr(agent_service, "ToolService", FakeToolService)
        out = agent_service.invoke_agent("alpha-bot", "Please fetch https://example.com", None)
        assert out["tool_used"] == "fetch"
        # Format is: "[alpha-bot] fetch: <url> (status=200, bytes=4)"
        assert "fetch:" in out["output"]
        assert "https://example.com" in out["output"]
        assert "(status=200, bytes=4)" in out["output"]
    finally:
        teardown_env(temp_dir)
        os.environ.pop("AGENT_CONFIG_DIR", None)


def test_invoke_agent_tool_not_found_fallback(monkeypatch):
    temp_dir = make_temp_agent_dir({"name": "Alpha Bot", "tools": ["web_search"]})
    try:
        os.environ["AGENT_CONFIG_DIR"] = temp_dir
        monkeypatch.setattr(agent_service, "ToolService", FakeToolService)
        # Force detect to select a non-existent tool handled by FakeToolService
        import src.agents.general_agent as general_agent

        def fake_detect(*args, **kwargs):
            return True, {"tool": "bad", "arguments": {"query": "x"}}

        monkeypatch.setattr(general_agent.GeneralAgent, "detect_tool_request", fake_detect)
        out = agent_service.invoke_agent("alpha-bot", "cause tool not found", None)
        assert "Echo:" in out["output"]
    finally:
        teardown_env(temp_dir)
        os.environ.pop("AGENT_CONFIG_DIR", None)


def test_invoke_agent_unexpected_error_fallback(monkeypatch):
    temp_dir = make_temp_agent_dir({"name": "Alpha Bot", "tools": ["web_search"]})
    try:
        os.environ["AGENT_CONFIG_DIR"] = temp_dir
        monkeypatch.setattr(agent_service, "ToolService", FakeToolService)
        import src.agents.general_agent as general_agent

        def fake_detect(*args, **kwargs):
            return True, {"tool": "explode", "arguments": {"query": "x"}}

        monkeypatch.setattr(general_agent.GeneralAgent, "detect_tool_request", fake_detect)
        out = agent_service.invoke_agent("alpha-bot", "boom", None)
        assert "Echo:" in out["output"]
    finally:
        teardown_env(temp_dir)
        os.environ.pop("AGENT_CONFIG_DIR", None)


def test_agent_service_sanitize_url():
    s = "'(`https://ex.com/path,)'"
    clean = agent_service._sanitize_url(s)
    assert clean == "https://ex.com/path"


def test_invoke_agent_returns_session_id(monkeypatch):
    temp_dir = make_temp_agent_dir({"name": "Alpha Bot", "tools": ["web_search"]})
    try:
        os.environ["AGENT_CONFIG_DIR"] = temp_dir
        monkeypatch.setattr(agent_service, "ToolService", FakeToolService)
        out = agent_service.invoke_agent("alpha-bot", "hello", "session-1")
        assert "session_id" in out and isinstance(out["session_id"], str)
    finally:
        teardown_env(temp_dir)
        os.environ.pop("AGENT_CONFIG_DIR", None)
