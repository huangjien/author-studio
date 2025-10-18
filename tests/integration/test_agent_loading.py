import os
import textwrap


def test_load_valid_config_on_startup(tmp_path):
    # Arrange: create a valid YAML in agent_configs/
    target_dir = os.path.join(os.getcwd(), "agent_configs")
    os.makedirs(target_dir, exist_ok=True)
    yaml_path = os.path.join(target_dir, "example_agent.yaml")
    with open(yaml_path, "w") as f:
        f.write(
            textwrap.dedent(
                """
            name: example_agent
            llm:
              provider: openai
              model: gpt-4o-mini
            workflow:
              type: simple
              human_in_loop: optional
            prompts:
              en: "You are a helpful assistant."
              es: "Eres un asistente útil."
            tools:
              - web_search
            """
            )
        )

    # Act: Use the loader to read configs
    from src.config.loader import load_agent_configs  # to be implemented

    configs = load_agent_configs(target_dir)

    # Assert: at least one config loaded
    assert len(configs) >= 1
    assert any(c.name == "example_agent" for c in configs)
