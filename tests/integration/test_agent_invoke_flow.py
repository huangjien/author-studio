import os

from fastapi.testclient import TestClient

API_KEY = "test-key"


def setup_env(tmp_path):
    os.environ["API_KEY"] = API_KEY
    target_dir = os.path.join(str(tmp_path), "agent_configs")
    os.environ["AGENT_CONFIG_DIR"] = target_dir
    os.makedirs(target_dir, exist_ok=True)
    with open(os.path.join(target_dir, "alpha.yaml"), "w") as f:
        f.write(
            """
            name: Alpha Bot
            llm:
              provider: openai
              model: gpt-4o-mini
            workflow:
              type: single_step
            prompts:
              en: "Hello"
            tools: []
            """
        )
    return target_dir


def test_end_to_end_invoke_flow_success_and_session_continue(tmp_path):
    target_dir = setup_env(tmp_path)
    from src.agents.registry import AgentRegistry
    from src.main import app  # import after env set

    # Ensure registry has the agent
    registry = AgentRegistry()
    registry.reload(dir_path=target_dir)

    client = TestClient(app)
    # First invoke -> should create a session
    resp1 = client.post(
        "/agents/alpha-bot/invoke",
        headers={"X-API-Key": API_KEY},
        json={"input": "Hello World!"},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["agent_id"] == "alpha-bot"
    assert "session_id" in data1
    assert "output" in data1 and "Echo" in data1["output"]

    # Second invoke -> continue same session
    resp2 = client.post(
        "/agents/alpha-bot/invoke",
        headers={"X-API-Key": API_KEY},
        json={"input": "Second message", "session_id": data1["session_id"]},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["agent_id"] == "alpha-bot"
    assert data2["session_id"] == data1["session_id"]
    assert "Echo" in data2["output"]


def test_invoke_returns_401_when_api_key_invalid(tmp_path):
    setup_env(tmp_path)
    from src.main import app

    client = TestClient(app)

    resp = client.post(
        "/agents/alpha-bot/invoke",
        headers={"X-API-Key": "wrong-key"},
        json={"input": "Hello"},
    )
    assert resp.status_code == 401


def test_invoke_returns_404_for_unknown_agent(tmp_path):
    setup_env(tmp_path)
    from src.main import app

    client = TestClient(app)

    resp = client.post(
        "/agents/unknown/invoke",
        headers={"X-API-Key": API_KEY},
        json={"input": "Hello"},
    )
    assert resp.status_code == 404


def test_invoke_returns_500_when_autogen_reports_error(tmp_path, monkeypatch):
    setup_env(tmp_path)
    import src.api.routes.agents as agents_routes
    from src.main import app

    # Force async support and patch async run to return an error
    monkeypatch.setattr(agents_routes, "autogen_supports_async", lambda: True)

    async def _fake_run_error(*a, **k):
        return {"ok": False, "error": "AutoGen toolchain failed"}

    monkeypatch.setattr(agents_routes, "run_single_turn_async", _fake_run_error)

    client = TestClient(app)
    resp = client.post(
        "/agents/alpha-bot/invoke",
        headers={"X-API-Key": API_KEY},
        json={"input": "Trigger error"},
    )
    assert resp.status_code == 500


def test_invoke_with_mcp_directive_process_web_search(tmp_path, monkeypatch):
    target_dir = setup_env(tmp_path)
    # Update agent YAML to include a process MCP server supporting fetch/web_search
    with open(os.path.join(target_dir, "alpha.yaml"), "w") as f:
        f.write(
            """
            name: Alpha Bot
            llm:
              provider: openai
              model: gpt-4o-mini
            workflow:
              type: single_step
            prompts:
              en: "Hello"
            tools: []
            mcp_servers:
              - name: proc-fetch
                type: process
                tools: ["fetch", "web_search"]
                command: mcp-server-fetch
                persistent: true
            """
        )

    # Patch the agents route to always use async path and return a directive
    import src.api.routes.agents as agents_routes

    monkeypatch.setattr(agents_routes, "autogen_supports_async", lambda: True)
    monkeypatch.setattr(agents_routes, "autogen_available", lambda: True)
    directive = (
        'MCP_DIRECTIVE: {"tool": "web_search", "provider": "process", '
        '"arguments": {"query": "LangChain", "top_n": 1}}'
    )

    async def _fake_run(*a, **k):
        return {
            "ok": True,
            "chat_result": f"Echo: test. {directive}",
            "session_selected_language": "en",
        }

    monkeypatch.setattr(
        agents_routes,
        "run_single_turn_async",
        _fake_run,
    )

    # Patch MCP manager to return a fake client
    import src.services.mcp_manager as mcp_manager

    class FakeClient:
        def call_tool(self, name, args_dict, timeout=5.0):
            if name == "fetch":
                # Simulate Wikipedia API body
                body = {
                    "query": {
                        "search": [{"title": "LangChain", "snippet": "A framework for LLM apps."}]
                    }
                }
                import json as _json

                return {
                    "status": 200,
                    "body": _json.dumps(body),
                    "headers": {},
                    "url": args_dict.get("url", ""),
                }
            return {"status": 400, "body": "", "headers": {}, "url": ""}

    class FakeMgr:
        def acquire(self, *args, **kwargs):
            return FakeClient()

        def restart(self, *args, **kwargs):
            return FakeClient()

    monkeypatch.setattr(mcp_manager, "mcp_client_manager", FakeMgr())

    from src.config.env import settings
    from src.main import app

    settings.agent_config_dir = target_dir
    print("DEBUG settings.agent_config_dir set to:", settings.agent_config_dir)

    client = TestClient(app)
    resp = client.post(
        "/agents/alpha-bot/invoke",
        headers={"X-API-Key": API_KEY},
        json={"input": "Use web_search."},
    )
    print("DEBUG status:", resp.status_code)
    print("DEBUG body:", resp.text)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("tool_used") == "web_search"
    tool_res = data.get("tool_result")
    assert isinstance(tool_res, dict)
    assert tool_res.get("provider") == "process"
    assert tool_res.get("server") == "proc-fetch"
    payload = tool_res.get("data")
    assert isinstance(payload, dict)
    assert payload.get("tool") == "web_search"
    results = payload.get("results")
    assert isinstance(results, list) and len(results) == 1
    assert results[0]["title"] == "LangChain"
