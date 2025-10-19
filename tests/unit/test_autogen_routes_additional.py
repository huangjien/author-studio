import importlib
import json
from pathlib import Path

from fastapi.testclient import TestClient


def write_agent_yaml(
    tmpdir: Path, name: str, workflow: dict | None = None, prompts: dict | None = None
):
    cfg = {
        "name": name,
        "llm": {"provider": "openai", "model": "gpt-4o-mini"},
        "workflow": workflow or {},
        "prompts": prompts or {"en": "You are a helpful assistant."},
    }
    (tmpdir / (name.lower().replace(" ", "_") + ".yaml")).write_text(json.dumps(cfg))


def _reload_for_env(monkeypatch, tmp_path):
    # Reload settings and modules after environment changes
    import src.config.env as envmod

    importlib.reload(envmod)
    import src.api.routes.autogen as autogen_routes

    importlib.reload(autogen_routes)
    import src.main as appmod

    importlib.reload(appmod)
    return autogen_routes, appmod


def test_async_path_success(monkeypatch, tmp_path):
    # Enable endpoint
    monkeypatch.setenv("AUTOGEN_ENABLED", "1")
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(tmp_path))

    # Create autogen agent
    write_agent_yaml(tmp_path, "Async Bot", workflow={"type": "autogen"})

    autogen_routes, appmod = _reload_for_env(monkeypatch, tmp_path)

    # Force availability and async support, patch async adapter result
    autogen_routes.autogen_available = lambda: True
    autogen_routes.autogen_supports_async = lambda: True
    invoked = {}

    async def fake_async_run(agent, text):
        invoked["agent_id"] = agent.agent_id
        invoked["text"] = text
        return {
            "ok": True,
            "agent_id": agent.agent_id,
            "input": text,
            "llm_config": agent.llm_config,
            "chat_result": "async-ok",
        }

    autogen_routes.run_single_turn_async = fake_async_run

    c = TestClient(appmod.app)
    resp = c.post(
        f"/autogen/{'async-bot'}/invoke", headers={"X-API-Key": "secret"}, json={"input": "Hello"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["chat_result"] == "async-ok"
    # Verify our async adapter was used with the right params
    assert invoked["agent_id"] == "async-bot"
    assert invoked["text"] == "Hello"


def test_422_when_missing_input(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOGEN_ENABLED", "1")
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(tmp_path))
    write_agent_yaml(tmp_path, "Zeta Bot", workflow={"type": "autogen"})

    autogen_routes, appmod = _reload_for_env(monkeypatch, tmp_path)
    autogen_routes.autogen_available = lambda: True
    autogen_routes.autogen_supports_async = lambda: False
    autogen_routes.run_single_turn = lambda agent, text: {"ok": True, "chat_result": "ok"}

    c = TestClient(appmod.app)
    # Missing body entirely -> 422
    resp1 = c.post(f"/autogen/{'zeta-bot'}/invoke", headers={"X-API-Key": "secret"})
    assert resp1.status_code == 422
    # Body present but missing 'input' -> 422
    resp2 = c.post(f"/autogen/{'zeta-bot'}/invoke", headers={"X-API-Key": "secret"}, json={})
    assert resp2.status_code == 422


def test_async_adapter_raises_returns_500(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOGEN_ENABLED", "1")
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(tmp_path))
    write_agent_yaml(tmp_path, "Error Bot", workflow={"type": "autogen"})

    autogen_routes, appmod = _reload_for_env(monkeypatch, tmp_path)
    autogen_routes.autogen_available = lambda: True
    autogen_routes.autogen_supports_async = lambda: True

    async def raising_adapter(agent, text):
        raise RuntimeError("adapter-failure")

    autogen_routes.run_single_turn_async = raising_adapter

    c = TestClient(appmod.app)
    resp = c.post(
        f"/autogen/{'error-bot'}/invoke", headers={"X-API-Key": "secret"}, json={"input": "Hello"}
    )
    assert resp.status_code == 500
