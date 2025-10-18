import os


def test_invalid_yaml_logs_error_and_skips_agent(tmp_path, capsys):
    # Arrange: write an invalid YAML file
    target_dir = os.path.join(os.getcwd(), "agent_configs")
    os.makedirs(target_dir, exist_ok=True)
    bad_path = os.path.join(target_dir, "bad_agent.yaml")
    with open(bad_path, "w") as f:
        f.write("name: bad_agent\nllm: [this: is not: yaml\n")  # malformed YAML

    # Act: attempt to load
    from src.config.loader import load_agent_configs  # to be implemented
    configs = load_agent_configs(target_dir)

    # Assert: bad agent skipped
    assert not any(getattr(c, "name", None) == "bad_agent" for c in configs)