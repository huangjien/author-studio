import os
import shutil
import tempfile
import types

import src.services.agent_service as agent_service


def make_temp_agent_dir(yaml_payload: dict) -> str:
    temp_dir = tempfile.mkdtemp(prefix="agent_cfg_")
    cfg_path = os.path.join(temp_dir, "alpha.yaml")
    import yaml

    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(yaml_payload, f, sort_keys=False)
    return temp_dir


def teardown_env(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


def test__detect_tool_request_fetch_prefer_http_sanitizes_url(monkeypatch):
    # Force support check to return True to exercise internal detect function
    monkeypatch.setattr(agent_service, "_agent_supports_tool", lambda a, t: True)
    # Minimal fake agent object
    fake_agent = types.SimpleNamespace(agent_id="alpha-bot", tools=["fetch"], mcp_servers=[])
    selection = agent_service._detect_tool_request(
        fake_agent, "See (https://example.com), prefer http"
    )
    assert selection is not None
    tool, args = selection
    assert tool == "fetch"
    assert args["url"] == "https://example.com"
    assert args["prefer"] == "http"


def test__detect_tool_request_web_search_topn_and_prefer_process(monkeypatch):
    monkeypatch.setattr(agent_service, "_agent_supports_tool", lambda a, t: True)
    fake_agent = types.SimpleNamespace(agent_id="alpha-bot", tools=["web_search"], mcp_servers=[])
    text = "Search for AI top 3 prefer process"
    selection = agent_service._detect_tool_request(fake_agent, text)
    assert selection is not None
    tool, args = selection
    assert tool == "web_search"
    assert args["query"] == text
    assert args["top_n"] == 3
    assert args["prefer"] == "process"


def test__detect_tool_request_prefer_local(monkeypatch):
    monkeypatch.setattr(agent_service, "_agent_supports_tool", lambda a, t: True)
    fake_agent = types.SimpleNamespace(agent_id="alpha-bot", tools=["web_search"], mcp_servers=[])
    text = "Find docs prefer local"
    selection = agent_service._detect_tool_request(fake_agent, text)
    assert selection is not None
    tool, args = selection
    assert tool == "web_search"
    assert args["prefer"] == "local"


def test__agent_supports_tool_exception_returns_false(monkeypatch):
    class TS:
        def list_tools(self, agent_id):
            return {"agent_id": agent_id, "tools": []}

    monkeypatch.setattr(agent_service, "ToolService", TS)
    broken_agent = types.SimpleNamespace(agent_id="alpha-bot")  # no tools/mcp_servers
    assert agent_service._agent_supports_tool(broken_agent, "fetch") is False


def test_invoke_agent_web_search_results_list_summarization(monkeypatch):
    temp_dir = make_temp_agent_dir({"name": "Alpha Bot", "tools": ["web_search"]})
    try:
        os.environ["AGENT_CONFIG_DIR"] = temp_dir

        class StubTS:
            def invoke(self, agent_id, tool_name, args):
                return {
                    "tool": "web_search",
                    "query": args.get("query", ""),
                    "results": [
                        {"title": "Python", "url": "https://www.python.org"},
                        {"name": "PyPI", "link": "https://pypi.org"},
                    ],
                }

        monkeypatch.setattr(agent_service, "ToolService", StubTS)
        out = agent_service.invoke_agent("alpha-bot", "Search Python", None)
        assert out["tool_used"] == "web_search"
        assert "web_search results:" in out["output"]
        assert "1. Python - https://www.python.org" in out["output"]
        assert "2. PyPI - https://pypi.org" in out["output"]
    finally:
        teardown_env(temp_dir)
        os.environ.pop("AGENT_CONFIG_DIR", None)


def test_invoke_agent_echo_with_prompt_prefix(monkeypatch):
    # Create agent with localized prompt to trigger compute_output prefix branch
    temp_dir = make_temp_agent_dir({"name": "Alpha Bot", "prompts": {"en": "Hello"}})
    try:
        os.environ["AGENT_CONFIG_DIR"] = temp_dir
        out = agent_service.invoke_agent("alpha-bot", "Testing echo", None, language="en")
        assert out["output"].startswith("[alpha-bot] Hello :: Echo: Testing echo")
        assert out.get("tool_used") is None
    finally:
        teardown_env(temp_dir)
        os.environ.pop("AGENT_CONFIG_DIR", None)


def test__sanitize_url_various_cases():
    assert agent_service._sanitize_url(None) == ""
    assert agent_service._sanitize_url("  'https://a.com',,") == "https://a.com"
    assert agent_service._sanitize_url("`<https://b.com>`") == "https://b.com"


def test__agent_supports_tool_list_tools_error_fallback(monkeypatch):
    class ErrTS:
        def list_tools(self, agent_id):
            raise RuntimeError("boom")

    monkeypatch.setattr(agent_service, "ToolService", ErrTS)
    fake_agent = types.SimpleNamespace(agent_id="alpha-bot", tools=["fetch"], mcp_servers=[])
    assert agent_service._agent_supports_tool(fake_agent, "fetch") is True


def test_invoke_agent_web_search_empty_results_and_resp_includes_tool_result(monkeypatch):
    temp_dir = make_temp_agent_dir({"name": "Alpha Bot", "tools": ["web_search"]})
    try:
        os.environ["AGENT_CONFIG_DIR"] = temp_dir

        class StubTS:
            def invoke(self, agent_id, tool_name, args):
                return {"tool": "web_search", "query": args.get("query", ""), "results": []}

        monkeypatch.setattr(agent_service, "ToolService", StubTS)
        out = agent_service.invoke_agent("alpha-bot", "Search AI", None)
        assert out["tool_used"] == "web_search"
        # Fallback summary should be used when results list is empty
        assert "web_search:" in out["output"]
        assert "results:" not in out["output"]
        # Ensure tool_result is included in response payload
        assert isinstance(out.get("tool_result"), dict)
        assert out["tool_result"].get("results") == []
    finally:
        teardown_env(temp_dir)
        os.environ.pop("AGENT_CONFIG_DIR", None)
