import json
import os
import shutil
import sys
import tempfile

import pytest

from src.services.tool_service import ToolNotFoundError, ToolService


def make_temp_agent_dir(yaml_payload: dict) -> str:
    temp_dir = tempfile.mkdtemp(prefix="agent_cfg_")
    cfg_path = os.path.join(temp_dir, "alpha.yaml")
    import yaml

    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(yaml_payload, f, sort_keys=False)
    return temp_dir


def teardown_env(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


def test_resolve_servers_ordering_prefer_http():
    ts = ToolService(dir_path="agent_configs")
    agent = {
        "agent_id": "alpha-bot",
        "tools": ["web_search"],
        "mcp_servers": [
            {
                "name": "proc-low",
                "type": "process",
                "tools": ["web_search"],
                "priority": "low",
                "persistent": True,
            },
            {"name": "http-high", "type": "http", "tools": ["web_search"], "priority": "high"},
            {"name": "local", "type": "local", "tools": ["web_search"]},
        ],
    }
    args = {"query": "wikipedia python", "prefer": "http"}
    ordered = ts._resolve_servers(agent, "web_search", args)
    assert ordered and ordered[0]["name"] == "http-high"


def test_invoke_http_missing_url_raises():
    ts = ToolService(dir_path="agent_configs")
    server = {"type": "http", "tools": ["web_search"], "name": "bad-http"}
    with pytest.raises(ToolNotFoundError):
        ts._invoke_on_server(server, "alpha", "web_search", {"query": "hello"})


def test_invoke_http_status_error(monkeypatch):
    ts = ToolService(dir_path="agent_configs")
    server = {
        "type": "http",
        "url": "http://example.com",
        "path_template": "/tools/{tool_name}/invoke",
        "tools": ["web_search"],
    }

    class FakeResp:
        def __init__(self, status_code=500):
            self.status_code = status_code

        def json(self):
            return {"error": "bad"}

    class FakeRequests:
        def post(self, url, json=None, headers=None, timeout=5):  # noqa: A003
            return FakeResp(500)

    monkeypatch.setitem(sys.modules, "requests", FakeRequests())

    with pytest.raises(ToolNotFoundError):
        ts._invoke_on_server(server, "alpha", "web_search", {"query": "hello"})


def test_invoke_http_exception(monkeypatch):
    ts = ToolService(dir_path="agent_configs")
    server = {
        "type": "http",
        "url": "http://example.com",
        "path_template": "/tools/{tool_name}/invoke",
        "tools": ["web_search"],
    }

    class BadRequests:
        def post(self, url, json=None, headers=None, timeout=5):  # noqa: A003
            raise RuntimeError("boom")

    monkeypatch.setitem(sys.modules, "requests", BadRequests())

    with pytest.raises(ToolNotFoundError):
        ts._invoke_on_server(server, "alpha", "web_search", {"query": "hello"})


def test_invoke_process_persistent_web_search_success(monkeypatch):
    ts = ToolService(dir_path="agent_configs")
    server = {
        "name": "proc-search",
        "type": "process",
        "tools": ["web_search", "fetch"],
        "command": "mcp-server-fetch",
        "persistent": True,
        "initialize_timeout": 0.01,
        "call_timeout": 0.01,
        "tool_call_retries": 0,
    }

    class FakeClient:
        def call_tool(self, tool, args_dict, timeout=0.01):
            if tool == "fetch":
                body = json.dumps(
                    {
                        "query": {
                            "search": [
                                {"title": "Alpha", "snippet": "a"},
                                {"title": "Beta", "snippet": "b"},
                            ]
                        }
                    }
                )
                return {"body": body}
            raise RuntimeError("unexpected tool")

    class FakeMgr:
        def acquire(self, **kwargs):
            return FakeClient()

        def restart(self, **kwargs):
            return FakeClient()

    import src.services.mcp_manager as mcp_manager

    monkeypatch.setattr(mcp_manager, "mcp_client_manager", FakeMgr())

    res = ts._invoke_on_server(server, "alpha", "web_search", {"query": "alpha", "top_n": 2})
    assert res["tool"] == "web_search"
    assert len(res["results"]) == 2
    assert res["results"][0]["title"] == "Alpha"


def test_invoke_process_ephemeral_fetch_success(monkeypatch):
    ts = ToolService(dir_path="agent_configs")
    server = {
        "name": "proc-fetch",
        "type": "process",
        "tools": ["fetch"],
        "command": "mcp-server-fetch",
        "persistent": False,
        "initialize_timeout": 0.01,
        "call_timeout": 0.01,
        "tool_call_retries": 0,
    }

    class FakeMCP:
        def __init__(self, command, args=None, env=None):
            pass

        def start(self):
            return None

        def initialize(self, timeout=0.01):
            return None

        def stop(self):
            return None

        def call_tool(self, tool, args_dict, timeout=0.01):
            assert tool == "fetch"
            return {
                "status": 200,
                "body": "OK",
                "headers": {},
                "url": args_dict.get("url", "http://x"),
                "content_type": "text/plain",
            }

    import src.services.mcp_client as mcp_client

    monkeypatch.setattr(mcp_client, "MCPClient", FakeMCP)
    monkeypatch.setattr(mcp_client, "MCPClientError", Exception)

    res = ts._invoke_on_server(server, "alpha", "fetch", {"url": "http://example.com"})
    assert res["tool"] == "fetch"
    assert res["results"][0]["status"] == 200


def test_invoke_unsupported_server_type():
    ts = ToolService(dir_path="agent_configs")
    server = {"name": "bad", "type": "stdio", "tools": ["web_search"]}
    with pytest.raises(ToolNotFoundError):
        ts._invoke_on_server(server, "alpha", "web_search", {"query": "x"})


def test_list_tools_aggregates_yaml_servers():
    temp_dir = make_temp_agent_dir(
        {
            "name": "Alpha Bot",
            "tools": [],
            "mcp_servers": [
                {"name": "proc", "type": "process", "tools": ["fetch"], "persistent": True},
                {"name": "local", "type": "local", "tools": ["web_search"]},
            ],
        }
    )
    try:
        ts = ToolService(dir_path=temp_dir)
        tools = ts.list_tools("alpha-bot")
        names = tools.get("tools", [])
        assert "fetch" in names
        assert "web_search" in names
    finally:
        teardown_env(temp_dir)


def test_invoke_no_candidates_local_fetch(monkeypatch):
    temp_dir = make_temp_agent_dir({"name": "Alpha Bot", "tools": []})
    try:
        ts = ToolService(dir_path=temp_dir)

        class FakeLocalFetch:
            def fetch(self, url: str, timeout: float = 5.0):
                return {
                    "tool": "fetch",
                    "query": url,
                    "results": [{"status": 200, "body": "Hello", "headers": {}, "url": url}],
                }

        import src.tools.providers.local_fetch as local_fetch

        monkeypatch.setattr(local_fetch, "fetch", FakeLocalFetch().fetch)

        res = ts.invoke("alpha-bot", "fetch", {"url": "http://example.com"})
        assert res["tool"] == "fetch"
        assert res["results"][0]["status"] == 200
    finally:
        teardown_env(temp_dir)
