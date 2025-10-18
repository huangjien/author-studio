import importlib
import json
import os

from fastapi.testclient import TestClient

API_KEY = "test-key"


def setup_env(tmp_path):
    os.environ["API_KEY"] = API_KEY
    target_dir = os.path.join(str(tmp_path), "agent_configs")
    os.environ["AGENT_CONFIG_DIR"] = target_dir
    os.environ["DATA_DIR"] = os.path.join(str(tmp_path), ".data")
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


def test_persisted_session_history_includes_role_entries_and_echo(tmp_path):
    # Configure environment and agent, with DATA_DIR for FileStore
    target_dir = setup_env(tmp_path)

    # Reload settings and services to pick up env changes within the same test session
    import src.config.env as env_module

    importlib.reload(env_module)
    import src.services.session_service as session_module

    importlib.reload(session_module)
    import src.services.agent_service as agent_module

    importlib.reload(agent_module)

    # Ensure registry sees the agent
    from src.agents.registry import AgentRegistry

    registry = AgentRegistry()
    registry.reload(dir_path=target_dir)

    import src.main as main_module

    importlib.reload(main_module)
    from src.main import app

    client = TestClient(app)

    input_text = "Hello persistence!"
    resp = client.post(
        "/agents/alpha-bot/invoke",
        headers={"X-API-Key": API_KEY},
        json={"input": input_text},
    )
    assert resp.status_code == 200
    data = resp.json()
    session_id = data["session_id"]

    # Load the persisted session file from DATA_DIR
    data_dir = os.environ["DATA_DIR"]
    fpath = os.path.join(data_dir, f"session_{session_id}.json")
    assert os.path.exists(fpath)
    with open(fpath, "r") as f:
        payload = json.load(f)

    history = payload.get("history", [])
    assert len(history) >= 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == input_text
    assert history[1]["role"] == "agent"
    assert "Echo" in history[1]["content"]
    assert "alpha-bot" in history[1]["content"]
