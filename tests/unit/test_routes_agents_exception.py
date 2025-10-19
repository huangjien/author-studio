import os

from fastapi.testclient import TestClient


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
    # Cause the AutoGen adapter to fail
    import src.api.routes.agents as routes
    from src.main import app

    async def bad_run(*args, **kwargs):
        raise RuntimeError("Kaboom")

    monkeypatch.setattr(routes, "run_single_turn_async", bad_run, raising=True)

    client = TestClient(app)
    resp = client.post(
        "/agents/alpha-bot/invoke",
        headers={"X-API-Key": api_key},
        json={"input": "Hello"},
    )
    assert resp.status_code == 500
