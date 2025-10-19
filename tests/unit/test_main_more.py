import os

from fastapi.testclient import TestClient

import src.main as main
from src.core.models.agent import Agent


def test_detect_llm_providers_flags():
    env = {
        "OPENAI_API_KEY": "tok",
        "ANTHROPIC_API_KEY": "tok",
        "GEMINI_API_KEY": "tok",
        "AZURE_OPENAI_API_KEY": "tok",
        "AZURE_OPENAI_ENDPOINT": "https://myazure.endpoint",
        "MISTRAL_API_KEY": "tok",
        "COHERE_API_KEY": "tok",
        "TOGETHER_API_KEY": "tok",
        "DEEPSEEK_API_KEY": "tok",
        "OLLAMA_HOST": "http://localhost:11434",
        "OLLAMA_PORT": "11434",
    }

    providers = main._detect_llm_providers(env)

    assert providers["openai"]["configured"] is True
    assert providers["anthropic"]["configured"] is True
    assert providers["gemini"]["configured"] is True
    assert providers["azure_openai"]["configured"] is True
    assert providers["mistral"]["configured"] is True
    assert providers["cohere"]["configured"] is True
    assert providers["together"]["configured"] is True
    assert providers["deepseek"]["configured"] is True
    assert providers["ollama"]["configured"] is True
    assert providers["ollama"]["details"]["resolved_host"] == env["OLLAMA_HOST"]
    assert "chat_completions" in providers["deepseek"]["details"]


def test_detect_llm_providers_ollama_default_host_when_not_set():
    env = {"OLLAMA_PORT": "12345"}
    providers = main._detect_llm_providers(env)
    assert providers["ollama"]["configured"] is False
    assert providers["ollama"]["available"] is False
    assert providers["ollama"]["details"]["resolved_host"].startswith("http://localhost:12345")


def test_probe_http_success(monkeypatch):
    class FakeResp:
        def __init__(self, status_code):
            self.status_code = status_code

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None):
            return FakeResp(200)

    monkeypatch.setattr(main.httpx, "Client", FakeClient)
    result = main._probe_http("http://example.com")
    assert result["ok"] is True
    assert result["status_code"] == 200
    assert result["error"] is None
    assert isinstance(result["latency_ms"], float)


def test_probe_http_error(monkeypatch):
    class ErrClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, headers=None):
            raise RuntimeError("boom")

    monkeypatch.setattr(main.httpx, "Client", ErrClient)
    result = main._probe_http("http://example.com")
    assert result["ok"] is False
    assert result["status_code"] is None
    assert isinstance(result["error"], str)
    assert isinstance(result["latency_ms"], float)


def test_live_connectivity_all_providers(monkeypatch):
    def stub_probe_http(url, headers=None, timeout_ms=2000):
        return {"ok": True, "status_code": 200, "latency_ms": 1.23, "error": None}

    monkeypatch.setattr(main, "_probe_http", stub_probe_http)
    env = {
        "OPENAI_API_KEY": "tok",
        "ANTHROPIC_API_KEY": "tok",
        "GEMINI_API_KEY": "tok",
        "AZURE_OPENAI_API_KEY": "tok",
        "AZURE_OPENAI_ENDPOINT": "https://myazure.endpoint",
        "MISTRAL_API_KEY": "tok",
        "COHERE_API_KEY": "tok",
        "TOGETHER_API_KEY": "tok",
        "DEEPSEEK_API_KEY": "tok",
        "OLLAMA_HOST": "http://localhost:9251",
        "OLLAMA_PORT": "9252",
    }
    providers = main._detect_llm_providers(env)
    res = main._live_connectivity(env, providers, targets=None, timeout_ms=100)
    expected_keys = {
        "ollama",
        "openai",
        "anthropic",
        "gemini",
        "azure_openai",
        "mistral",
        "cohere",
        "together",
        "deepseek",
    }
    assert set(res["results"].keys()) == expected_keys
    assert res["results"]["ollama"]["endpoint"].endswith("/api/tags")
    assert res["results"]["ollama"]["configured"] is True
    assert res["live_ok"] is True


def test_live_connectivity_empty_when_no_targets_match(monkeypatch):
    def stub_probe_http(url, headers=None, timeout_ms=2000):
        return {"ok": True, "status_code": 200, "latency_ms": 1.23, "error": None}

    monkeypatch.setattr(main, "_probe_http", stub_probe_http)
    env = {"OPENAI_API_KEY": "tok"}
    providers = main._detect_llm_providers(env)
    res = main._live_connectivity(env, providers, targets=["bogus"], timeout_ms=50)
    assert res["results"] == {}
    assert res["live_ok"] is False


def test_health_endpoint_live_targets(monkeypatch):
    class FakeAgentRegistry:
        def __init__(self):
            self._agents = [
                Agent(
                    agent_id="alpha",
                    llm_config={"provider": "openai", "model": "gpt-4-turbo"},
                    workflow={},
                    prompts={"en": "Hello"},
                ),
                Agent(
                    agent_id="beta",
                    llm_config={"provider": "anthropic", "model": "claude"},
                    workflow={},
                    prompts={"en": "Hi", "zh": "你好"},
                ),
            ]

        def reload(self, dir_path: str) -> None:
            return None

        def list_agents(self):
            return self._agents

        def count(self) -> int:
            return len(self._agents)

    def fake_live(env, base_providers, targets=None, timeout_ms=2000):
        targets = targets or []
        results = {
            name: {"ok": True, "status_code": 200, "latency_ms": 0.1, "error": None}
            for name in targets
        }
        return {"results": results, "live_ok": True}

    monkeypatch.setattr(main, "AgentRegistry", FakeAgentRegistry)
    monkeypatch.setattr(main, "_live_connectivity", fake_live)
    monkeypatch.setenv("OPENAI_API_KEY", "tok")

    with TestClient(main.app) as client:
        resp = client.get("/health", params={"live": True, "providers": "openai,gemini"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "llm_providers" in data
        assert "agents" in data
        assert isinstance(data["agents"], list)
        # Live result includes only requested providers
        assert set(data["live"]["results"].keys()) == {"openai", "gemini"}
        assert data["live"]["live_ok"] is True


def test_health_lazy_build_without_startup(monkeypatch):
    class FakeAgentRegistry:
        def __init__(self):
            self._agents = [
                Agent(
                    agent_id="alpha",
                    llm_config={"provider": "openai", "model": "gpt-4-turbo"},
                    workflow={},
                    prompts={"en": "Hello"},
                )
            ]

        def reload(self, dir_path: str) -> None:
            return None

        def list_agents(self):
            return self._agents

        def count(self) -> int:
            return len(self._agents)

    monkeypatch.setattr(main, "AgentRegistry", FakeAgentRegistry)
    # Ensure cache is empty to exercise lazy build path
    monkeypatch.setattr(main, "HEALTH_INFO", {})
    # Call route function directly to avoid startup hook populating the cache
    data = main.health_check(live=False)
    assert data["status"] == "ok"
    assert "llm_providers" in data
    assert "agents" in data
    assert data["agent_count"] == 1


def test_favicon_serves_ico_when_present():
    with TestClient(main.app) as client:
        resp = client.get("/favicon.ico")
        # Should serve ICO if present
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("image/x-icon")


def test_favicon_fallback_to_png_when_ico_missing(monkeypatch):
    original_exists = main.os.path.exists

    def fake_exists(path):
        p = str(path)
        if p.endswith(os.path.join("src", "static", "favicon.ico")):
            return False
        return original_exists(path)

    monkeypatch.setattr(main.os.path, "exists", fake_exists)
    with TestClient(main.app) as client:
        resp = client.get("/favicon.ico")
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("image/png")


def test_favicon_404_when_both_missing(monkeypatch):
    def fake_exists(path):
        p = str(path)
        # Force both ico and png to appear missing
        if p.endswith(os.path.join("src", "static", "favicon.ico")):
            return False
        if p.endswith(os.path.join("src", "static", "favicon.png")):
            return False
        return False

    monkeypatch.setattr(main.os.path, "exists", fake_exists)
    with TestClient(main.app) as client:
        resp = client.get("/favicon.ico")
        assert resp.status_code == 404
        assert resp.json()["error"] == "favicon not found"
