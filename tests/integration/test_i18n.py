import os

from fastapi.testclient import TestClient

API_KEY = "test-key"


def setup_env(tmp_path):
    os.environ["API_KEY"] = API_KEY
    target_dir = os.path.join(str(tmp_path), "agent_configs")
    os.environ["AGENT_CONFIG_DIR"] = target_dir
    os.makedirs(target_dir, exist_ok=True)
    with open(os.path.join(target_dir, "example_agent.yaml"), "w") as f:
        f.write(
            """
name: example_agent
llm:
  provider: openai
  model: gpt-4o-mini
workflow:
  type: simple
prompts:
  en: "You are a helpful assistant."
  es: "Eres un asistente útil."
tools: []
            """
        )
    return target_dir


def test_i18n_accept_language_spanish(tmp_path):
    target_dir = setup_env(tmp_path)
    from src.agents.registry import AgentRegistry
    from src.main import app  # import after env set

    registry = AgentRegistry()
    registry.reload(dir_path=target_dir)

    client = TestClient(app)
    resp = client.post(
        "/agents/example-agent/invoke",
        headers={"X-API-Key": API_KEY, "Accept-Language": "es"},
        json={"input": "Hola"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_id"] == "example-agent"
    assert data.get("selected_language") in ("es", "es-es")
    assert isinstance(data.get("output"), str)


def test_i18n_accept_language_spanish_region(tmp_path):
    target_dir = setup_env(tmp_path)
    from src.agents.registry import AgentRegistry
    from src.main import app

    registry = AgentRegistry()
    registry.reload(dir_path=target_dir)

    client = TestClient(app)
    resp = client.post(
        "/agents/example-agent/invoke",
        headers={"X-API-Key": API_KEY, "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"},
        json={"input": "Hola"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("selected_language") in ("es", "es-es")
    assert isinstance(data.get("output"), str)


def test_i18n_fallback_to_english(tmp_path):
    target_dir = setup_env(tmp_path)
    from src.agents.registry import AgentRegistry
    from src.main import app

    registry = AgentRegistry()
    registry.reload(dir_path=target_dir)

    client = TestClient(app)
    resp = client.post(
        "/agents/example-agent/invoke",
        headers={"X-API-Key": API_KEY, "Accept-Language": "de"},
        json={"input": "Hallo"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("selected_language") in ("en", "en-us", "en-gb")
    assert isinstance(data.get("output"), str)


def test_i18n_q_value_weighting(tmp_path):
    target_dir = setup_env(tmp_path)
    from src.agents.registry import AgentRegistry
    from src.main import app

    registry = AgentRegistry()
    registry.reload(dir_path=target_dir)

    client = TestClient(app)
    # Prefer es due to higher q
    resp = client.post(
        "/agents/example-agent/invoke",
        headers={"X-API-Key": API_KEY, "Accept-Language": "en;q=0.5,es;q=0.9"},
        json={"input": "Hola"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("selected_language") in ("es", "es-es")
    assert isinstance(data.get("output"), str)
