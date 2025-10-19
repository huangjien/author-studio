import os
import shutil
import tempfile

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


def test_invoke_agent_web_search_empty_results_fallback(monkeypatch):
    temp_dir = make_temp_agent_dir({"name": "Alpha Bot", "tools": ["web_search"]})
    try:
        os.environ["AGENT_CONFIG_DIR"] = temp_dir

        # Stub ToolService to return empty results list
        class StubTS:
            def invoke(self, agent_id, tool_name, args):
                return {"tool": "web_search", "query": args.get("query", ""), "results": []}

        monkeypatch.setattr(agent_service, "ToolService", StubTS)
        out = agent_service.invoke_agent("alpha-bot", "Search Python", None)
        assert out["tool_used"] == "web_search"
        # Fallback summary should include 'web_search:' and tool_result
        assert "web_search:" in out["output"]
        assert isinstance(out.get("tool_result"), dict)
    finally:
        teardown_env(temp_dir)
        os.environ.pop("AGENT_CONFIG_DIR", None)


def test_invoke_agent_unknown_tool_executed_message(monkeypatch):
    temp_dir = make_temp_agent_dir({"name": "Alpha Bot", "tools": ["custom"]})
    try:
        os.environ["AGENT_CONFIG_DIR"] = temp_dir
        # Force selection of an unknown tool and ensure agent supports it
        import src.agents.general_agent as general_agent

        def fake_detect(*args, **kwargs):
            return ("custom", {})

        monkeypatch.setattr(general_agent.GeneralAgent, "detect_tool_request", fake_detect)
        monkeypatch.setattr(agent_service, "_agent_supports_tool", lambda a, t: True)

        class StubTS:
            def invoke(self, agent_id, tool_name, args):
                return {"ok": True}

        monkeypatch.setattr(agent_service, "ToolService", StubTS)
        out = agent_service.invoke_agent("alpha-bot", "run custom", None)
        assert out["output"].startswith("[alpha-bot] Tool 'custom' executed.")
        assert out.get("tool_result") == {"ok": True}
    finally:
        teardown_env(temp_dir)
        os.environ.pop("AGENT_CONFIG_DIR", None)


def test_invoke_agent_fetch_bytes_body_length(monkeypatch):
    temp_dir = make_temp_agent_dir({"name": "Alpha Bot", "tools": ["fetch"]})
    try:
        os.environ["AGENT_CONFIG_DIR"] = temp_dir

        class StubTS:
            def list_tools(self, agent_id):  # ensure support
                return {"agent_id": agent_id, "tools": ["fetch"]}

            def invoke(self, agent_id, tool_name, args):
                return {
                    "tool": "fetch",
                    "query": args.get("url", ""),
                    "results": [
                        {
                            "status": 200,
                            "body": b"bytes-data",
                            "headers": {},
                            "url": args.get("url", ""),
                            "content_type": "application/octet-stream",
                        }
                    ],
                }

        monkeypatch.setattr(agent_service, "ToolService", StubTS)
        out = agent_service.invoke_agent("alpha-bot", "fetch https://example.org/file.bin", None)
        assert out["tool_used"] == "fetch"
        assert "bytes=" in out["output"]
        # length should match len(b"bytes-data")
        assert "bytes=10" in out["output"]
    finally:
        teardown_env(temp_dir)
        os.environ.pop("AGENT_CONFIG_DIR", None)


def test_invoke_agent_web_search_nonlist_results_fallback(monkeypatch):
    temp_dir = make_temp_agent_dir({"name": "Alpha Bot", "tools": ["web_search"]})
    try:
        os.environ["AGENT_CONFIG_DIR"] = temp_dir

        class StubTS:
            def invoke(self, agent_id, tool_name, args):
                return {"tool": "web_search", "query": args.get("query", ""), "results": {"bad": 1}}

        monkeypatch.setattr(agent_service, "ToolService", StubTS)
        out = agent_service.invoke_agent("alpha-bot", "Search something", None)
        assert out["tool_used"] == "web_search"
        assert "web_search:" in out["output"]
        assert isinstance(out.get("tool_result"), dict)
    finally:
        teardown_env(temp_dir)
        os.environ.pop("AGENT_CONFIG_DIR", None)


def test_invoke_agent_fetch_status_code_and_none_body(monkeypatch):
    temp_dir = make_temp_agent_dir({"name": "Alpha Bot", "tools": ["fetch"]})
    try:
        os.environ["AGENT_CONFIG_DIR"] = temp_dir

        class StubTS:
            def list_tools(self, agent_id):
                return {"agent_id": agent_id, "tools": ["fetch"]}

            def invoke(self, agent_id, tool_name, args):
                return {
                    "tool": "fetch",
                    "query": args.get("url", ""),
                    "results": [
                        {
                            "status_code": 204,
                            "body": None,
                            "headers": {},
                            "url": args.get("url", ""),
                        }
                    ],
                }

        monkeypatch.setattr(agent_service, "ToolService", StubTS)
        out = agent_service.invoke_agent("alpha-bot", "fetch https://example.org/no-content", None)
        assert out["tool_used"] == "fetch"
        assert "status=204" in out["output"]
        assert "bytes=0" in out["output"]
    finally:
        teardown_env(temp_dir)
        os.environ.pop("AGENT_CONFIG_DIR", None)


def test_invoke_agent_selection_rejected_by_support_check(monkeypatch):
    temp_dir = make_temp_agent_dir({"name": "Alpha Bot", "tools": ["fetch"]})
    try:
        os.environ["AGENT_CONFIG_DIR"] = temp_dir
        import src.agents.general_agent as general_agent

        def fake_detect(*args, **kwargs):
            return ("fetch", {"url": "https://example.com"})

        monkeypatch.setattr(general_agent.GeneralAgent, "detect_tool_request", fake_detect)
        # Reject tool support to force default echo
        monkeypatch.setattr(agent_service, "_agent_supports_tool", lambda a, t: False)
        out = agent_service.invoke_agent("alpha-bot", "fetch https://example.com", None)
        assert "Echo:" in out["output"]
        assert out.get("tool_used") is None
    finally:
        teardown_env(temp_dir)
        os.environ.pop("AGENT_CONFIG_DIR", None)
