import os

from fastapi.testclient import TestClient

# Contract: POST /agents/{agent_id}/invoke
# - 200 on success with JSON {agent_id, session_id, output}
# - 404 for unknown agent
# - 500 when internal error occurs

API_KEY = "test-key"


def setup_env(tmp_path):
    os.environ["API_KEY"] = API_KEY
    # Create a temp agent config dir and one agent
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


def test_invoke_success_returns_200_with_output(tmp_path):
    target_dir = setup_env(tmp_path)
    from src.agents.registry import AgentRegistry
    from src.main import app  # import after env set

    # Load registry from temp configs to ensure agent exists
    registry = AgentRegistry()
    registry.reload(dir_path=target_dir)

    client = TestClient(app)
    resp = client.post(
        "/agents/alpha-bot/invoke",
        headers={"X-API-Key": API_KEY},
        json={"input": "Hello"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_id"] == "alpha-bot"
    assert "output" in data and isinstance(data["output"], str)
    assert "session_id" in data


def test_invoke_unknown_agent_returns_404(tmp_path):
    setup_env(tmp_path)
    from src.main import app

    client = TestClient(app)

    resp = client.post(
        "/agents/unknown-agent/invoke",
        headers={"X-API-Key": API_KEY},
        json={"input": "Hello"},
    )
    assert resp.status_code == 404


def test_invoke_internal_error_returns_500(tmp_path, monkeypatch):
    setup_env(tmp_path)
    # Monkeypatch the AutoGen adapter to raise
    import src.api.routes.agents as routes
    from src.main import app

    async def boom(*args, **kwargs):
        raise RuntimeError("Kaboom")

    monkeypatch.setattr(routes, "run_single_turn_async", boom, raising=True)

    client = TestClient(app)
    resp = client.post(
        "/agents/alpha-bot/invoke",
        headers={"X-API-Key": API_KEY},
        json={"input": "Hello"},
    )
    assert resp.status_code == 500