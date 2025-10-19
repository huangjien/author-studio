import importlib
import json
from pathlib import Path

import pytest
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


@pytest.fixture
def client(monkeypatch, tmp_path):
    # Default: enable endpoint and set API key
    monkeypatch.setenv("AUTOGEN_ENABLED", "1")
    monkeypatch.setenv("API_KEY", "secret")
    # Point to temp agent configs
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(tmp_path))

    # Create a default autogen-capable agent
    write_agent_yaml(
        tmp_path, "Alpha AutoGen", workflow={"type": "autogen"}, prompts={"en": "You are helpful."}
    )

    # Reload settings so the feature flag is picked up
    import src.config.env as envmod

    importlib.reload(envmod)
    # Also reload autogen routes to capture new settings instance
    import src.api.routes.autogen as autogen_routes

    importlib.reload(autogen_routes)
    # Import app AFTER env is set so router is registered appropriately
    import src.main as appmod

    importlib.reload(appmod)
    return TestClient(appmod.app)


def test_endpoint_404_when_flag_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOGEN_ENABLED", "0")
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(tmp_path))
    import src.config.env as envmod

    importlib.reload(envmod)
    import src.api.routes.autogen as autogen_routes

    importlib.reload(autogen_routes)
    import src.main as appmod

    importlib.reload(appmod)
    c = TestClient(appmod.app)
    resp = c.post(
        "/autogen/alpha-autogen/invoke", headers={"X-API-Key": "secret"}, json={"input": "hi"}
    )
    assert resp.status_code == 404


def test_requires_api_key(client):
    # Missing header should be rejected when keys are configured
    resp = client.post("/autogen/alpha-autogen/invoke", json={"input": "Hello"})
    assert resp.status_code == 401


def test_agent_not_found(client):
    resp = client.post(
        "/autogen/missing/invoke", headers={"X-API-Key": "secret"}, json={"input": "Hello"}
    )
    assert resp.status_code == 404


def test_rejects_non_autogen_workflow(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOGEN_ENABLED", "1")
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(tmp_path))

    write_agent_yaml(tmp_path, "Beta Bot", workflow={"type": "single_step"})

    import src.config.env as envmod

    importlib.reload(envmod)
    import src.api.routes.autogen as autogen_routes

    importlib.reload(autogen_routes)
    import src.main as appmod

    importlib.reload(appmod)
    c = TestClient(appmod.app)

    resp = c.post(
        "/autogen/beta-bot/invoke", headers={"X-API-Key": "secret"}, json={"input": "Hello"}
    )
    assert resp.status_code == 400


def test_rejects_absent_workflow_type(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOGEN_ENABLED", "1")
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(tmp_path))

    write_agent_yaml(tmp_path, "Gamma Bot", workflow={})

    import src.config.env as envmod

    importlib.reload(envmod)
    import src.api.routes.autogen as autogen_routes

    importlib.reload(autogen_routes)
    import src.main as appmod

    importlib.reload(appmod)
    c = TestClient(appmod.app)

    resp = c.post(
        "/autogen/gamma-bot/invoke", headers={"X-API-Key": "secret"}, json={"input": "Hello"}
    )
    assert resp.status_code == 400


def test_returns_501_when_autogen_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOGEN_ENABLED", "1")
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(tmp_path))

    write_agent_yaml(tmp_path, "Delta Bot", workflow={"type": "autogen"})

    import src.config.env as envmod

    importlib.reload(envmod)
    import src.api.routes.autogen as autogen_routes

    importlib.reload(autogen_routes)
    # Ensure autogen_available returns False regardless of environment
    importlib.reload(autogen_routes)
    autogen_routes.autogen_available = lambda: False

    import src.main as appmod

    importlib.reload(appmod)
    c = TestClient(appmod.app)

    resp = c.post(
        "/autogen/delta-bot/invoke", headers={"X-API-Key": "secret"}, json={"input": "Hello"}
    )
    assert resp.status_code == 501


def test_success_when_adapter_returns_ok(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOGEN_ENABLED", "1")
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(tmp_path))

    write_agent_yaml(tmp_path, "Omega Bot", workflow={"type": "autogen"})

    import src.config.env as envmod

    importlib.reload(envmod)
    import src.api.routes.autogen as autogen_routes

    importlib.reload(autogen_routes)
    autogen_routes.autogen_available = lambda: True
    autogen_routes.autogen_supports_async = lambda: False
    autogen_routes.run_single_turn = lambda agent, text: {
        "ok": True,
        "agent_id": agent.agent_id,
        "input": text,
        "llm_config": agent.llm_config,
        "chat_result": "ok",
    }

    import src.main as appmod

    importlib.reload(appmod)
    c = TestClient(appmod.app)

    resp = c.post(
        "/autogen/omega-bot/invoke", headers={"X-API-Key": "secret"}, json={"input": "Hello"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["agent_id"] == "omega-bot"
    assert data["chat_result"] == "ok"


def test_error_when_adapter_returns_error(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTOGEN_ENABLED", "1")
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("AGENT_CONFIG_DIR", str(tmp_path))

    write_agent_yaml(tmp_path, "Theta Bot", workflow={"type": "autogen"})

    import src.config.env as envmod

    importlib.reload(envmod)
    import src.api.routes.autogen as autogen_routes

    importlib.reload(autogen_routes)
    autogen_routes.autogen_available = lambda: True
    autogen_routes.autogen_supports_async = lambda: False
    autogen_routes.run_single_turn = lambda agent, text: {"ok": False, "error": "boom"}

    import src.main as appmod

    importlib.reload(appmod)
    c = TestClient(appmod.app)

    resp = c.post(
        "/autogen/theta-bot/invoke", headers={"X-API-Key": "secret"}, json={"input": "Hello"}
    )
    assert resp.status_code == 500
