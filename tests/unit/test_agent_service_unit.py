import os
import importlib
import pytest


def setup_env(tmp_path):
    target_dir = os.path.join(str(tmp_path), "agent_configs")
    os.makedirs(target_dir, exist_ok=True)
    os.environ["AGENT_CONFIG_DIR"] = target_dir
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
    return target_dir


def test_invoke_agent_success_direct_call(tmp_path):
    setup_env(tmp_path)
    import src.services.agent_service as svc
    importlib.reload(svc)

    result = svc.invoke_agent("alpha-bot", "Hello")
    assert result["agent_id"] == "alpha-bot"
    assert "Echo" in result["output"]
    assert result["selected_language"] in ("en", "en-us")


def test_invoke_agent_raises_keyerror_for_unknown_agent(tmp_path):
    setup_env(tmp_path)
    import src.services.agent_service as svc
    importlib.reload(svc)

    with pytest.raises(KeyError):
        svc.invoke_agent("unknown", "Hi")