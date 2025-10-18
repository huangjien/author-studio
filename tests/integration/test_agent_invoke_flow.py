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
    from src.main import app  # import after env set
    from src.agents.registry import AgentRegistry

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