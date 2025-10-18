import os

from src.agents.registry import AgentRegistry

# Removed unused pytest import


def test_registry_logs_on_reload(tmp_path, caplog):
    target_dir = os.path.join(str(tmp_path), "agent_configs")
    os.makedirs(target_dir, exist_ok=True)

    # Create one agent config
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

    registry = AgentRegistry()
    with caplog.at_level("INFO"):
        registry.reload(dir_path=target_dir)

    text = caplog.text
    assert "Reloading agents from directory" in text
    assert "Loading agents from configs" in text
    assert "Registered agent 'alpha-bot'" in text
    assert "Agent registry loaded: 1 agents" in text
