import os

from fastapi.testclient import TestClient

from src.main import app


def setup_agent(tmp_path):
    # Create a minimal agent config for known agent
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
            """
        )


def test_list_agent_tools_keyerror_returns_404(monkeypatch, tmp_path):
    setup_agent(tmp_path)
    import src.api.routes.agents as routes

    class BadService:
        def list_tools(self, agent_id):  # noqa: A003
            raise KeyError("missing")

    monkeypatch.setattr(routes, "ToolService", BadService, raising=True)
    client = TestClient(app)
    resp = client.get("/agents/alpha-bot/tools")
    assert resp.status_code == 404


def test_invoke_tool_unknown_agent_returns_404():
    client = TestClient(app)
    resp = client.post(
        "/agents/unknown-agent/tools/web_search",
        json={"arguments": {"query": "x"}},
    )
    assert resp.status_code == 404


def test_invoke_tool_generic_error_returns_500(monkeypatch, tmp_path):
    setup_agent(tmp_path)
    import src.api.routes.agents as routes

    class BoomService:
        def invoke(self, agent_id: str, tool_name: str, arguments: dict):
            raise RuntimeError("boom")

    monkeypatch.setattr(routes, "ToolService", BoomService, raising=True)
    client = TestClient(app)
    resp = client.post(
        "/agents/alpha-bot/tools/web_search",
        json={"arguments": {"query": "x"}},
    )
    assert resp.status_code == 500
