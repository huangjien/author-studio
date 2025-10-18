import os

from src.agents.registry import AgentRegistry


def write_yaml(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def test_registry_loads_and_indexes_agents_from_yaml(tmp_path):
    target_dir = os.path.join(str(tmp_path), "agent_configs")
    os.makedirs(target_dir, exist_ok=True)

    write_yaml(
        os.path.join(target_dir, "alpha.yaml"),
        """
        name: Alpha Bot
        llm:
          provider: openai
          model: gpt-4o-mini
        workflow:
          type: single_step
          human_in_loop: optional
        prompts:
          en: "Hello"
        tools:
          - web_search
        """,
    )

    write_yaml(
        os.path.join(target_dir, "beta.yaml"),
        """
        name: Beta Bot
        llm:
          provider: anthropic
          model: claude-3-haiku
        workflow:
          type: chain
          human_in_loop: always
        prompts:
          en: "Hi"
        tools: []
        """,
    )

    registry = AgentRegistry()
    registry.reload(dir_path=target_dir)

    assert registry.count() == 2

    alpha = registry.get_agent("alpha-bot")
    beta = registry.get_agent("beta-bot")

    assert alpha is not None
    assert beta is not None
    assert {a.agent_id for a in registry.list_agents()} == {"alpha-bot", "beta-bot"}


def test_registry_skips_duplicate_agent_ids(tmp_path, caplog):
    target_dir = os.path.join(str(tmp_path), "agent_configs")
    os.makedirs(target_dir, exist_ok=True)

    # First Alpha
    write_yaml(
        os.path.join(target_dir, "alpha.yaml"),
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
        """,
    )

    # Duplicate Alpha - should be skipped
    write_yaml(
        os.path.join(target_dir, "alpha_dup.yaml"),
        """
        name: Alpha Bot
        llm:
          provider: openai
          model: gpt-4o-mini
        workflow:
          type: single_step
        prompts:
          en: "Hello again"
        tools: []
        """,
    )

    registry = AgentRegistry()
    with caplog.at_level("ERROR"):
        registry.reload(dir_path=target_dir)

    # Only one unique agent id should be registered
    assert registry.count() == 1

    # Ensure log mentions duplicate
    assert "Duplicate agent id" in caplog.text
