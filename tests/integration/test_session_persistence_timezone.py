import os
import json
from datetime import datetime

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


def test_persisted_session_created_at_is_timezone_aware(tmp_path):
    # Configure environment and agent
    target_dir = setup_env(tmp_path)

    # Patch session_service to use a tmp .data directory
    from src.services.session_service import session_service
    tmp_data_dir = os.path.join(str(tmp_path), ".data")
    os.makedirs(tmp_data_dir, exist_ok=True)
    # Switch the file store base_dir to tmp path for isolation
    session_service.file.base_dir = tmp_data_dir

    # Ensure registry sees the agent
    from src.agents.registry import AgentRegistry
    registry = AgentRegistry()
    registry.reload(dir_path=target_dir)

    from src.main import app
    client = TestClient(app)

    resp = client.post(
        "/agents/alpha-bot/invoke",
        headers={"X-API-Key": API_KEY},
        json={"input": "Hello timezone!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    session_id = data["session_id"]

    # Load the persisted session file from tmp .data
    fpath = os.path.join(tmp_data_dir, f"session_{session_id}.json")
    assert os.path.exists(fpath)
    with open(fpath, "r") as f:
        payload = json.load(f)

    ts = payload["created_at"]
    # Should include timezone information; accept 'Z' or offset
    assert ts.endswith("Z") or ts.endswith("+00:00") or ts.endswith("-00:00")

    # Ensure parseable into a timezone-aware datetime
    ts_norm = ts.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(ts_norm)
    assert parsed.tzinfo is not None