import os
from fastapi.testclient import TestClient
import importlib


def setup_env(tmp_path):
    api_key = "unit-key"
    os.environ["API_KEY"] = api_key
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
    return api_key


def test_invoke_route_generic_exception_returns_500(tmp_path, monkeypatch):
    api_key = setup_env(tmp_path)
    from src.main import app
    from src.services import agent_service as agent_service_module
    importlib.reload(agent_service_module)

    def boom(*args, **kwargs):
        raise RuntimeError("Kaboom")

    monkeypatch.setattr(agent_service_module, "invoke_agent", boom, raising=True)

    client = TestClient(app)
    resp = client.post(
        "/agents/alpha-bot/invoke",
        headers={"X-API-Key": api_key},
        json={"input": "Hello"},
    )
    assert resp.status_code == 500