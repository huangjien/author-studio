import os
import shutil
import tempfile

import src.services.agent_service as agent_service


def make_temp_agent_dir(yaml_payload: dict) -> str:
    temp_dir = tempfile.mkdtemp(prefix="agent_cfg_")
    cfg_path = os.path.join(temp_dir, "alpha.yaml")
    import yaml

    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(yaml_payload, f, sort_keys=False)
    return temp_dir


def teardown_env(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


def test_compute_output_with_prefix():
    out = agent_service.compute_output("alpha-bot", "Ping", "en", "Hello")
    assert out == "[alpha-bot] Hello :: Echo: Ping"


def test_agent_supports_tool_fallback_when_list_tools_raises(monkeypatch):
    class BadToolService:
        def list_tools(self, agent_id):  # noqa: A003
            raise RuntimeError("fail")

    monkeypatch.setattr(agent_service, "ToolService", BadToolService)
    agent = type(
        "A", (), {"agent_id": "alpha-bot", "tools": [], "mcp_servers": [{"tools": ["fetch"]}]}
    )
    assert agent_service._agent_supports_tool(agent, "fetch") is True


def test_detect_tool_request_url_sanitization(monkeypatch):
    monkeypatch.setattr(agent_service, "_agent_supports_tool", lambda a, t: True)
    agent = type("A", (), {})
    res = agent_service._detect_tool_request(agent, "Please open '(`https://ex.com/path,)' now")
    assert res and res[0] == "fetch"
    assert res[1]["url"] == "https://ex.com/path"


def test_detect_tool_request_search_top_n_and_prefer_process(monkeypatch):
    monkeypatch.setattr(agent_service, "_agent_supports_tool", lambda a, t: True)
    agent = type("A", (), {})
    res = agent_service._detect_tool_request(agent, "Search top 3 via process Python tips")
    assert res and res[0] == "web_search"
    assert res[1]["top_n"] == 3
    assert res[1]["prefer"] == "process"


def test_invoke_agent_localized_prompt_with_prefix(monkeypatch):
    temp_dir = make_temp_agent_dir(
        {"name": "Alpha Bot", "tools": [], "prompts": {"en": "Hello", "es": "Hola"}}
    )
    try:
        os.environ["AGENT_CONFIG_DIR"] = temp_dir
        # Ensure language selection returns Spanish
        monkeypatch.setattr(
            agent_service, "get_localized_prompt", lambda prompts, accept_lang: ("es", "Hola")
        )
        out = agent_service.invoke_agent("alpha-bot", "Ping", None, language="es-ES,es;q=0.9")
        assert out["selected_language"] == "es"
        assert "Hola :: Echo: Ping" in out["output"]
    finally:
        teardown_env(temp_dir)
        os.environ.pop("AGENT_CONFIG_DIR", None)
