import os
import importlib

from src.config.loader import load_agent_configs


def write_file(path: str, content: str):
    with open(path, "w") as f:
        f.write(content)


def test_load_agent_configs_handles_valid_and_invalid_files(tmp_path, monkeypatch):
    target_dir = os.path.join(str(tmp_path), "agent_configs")
    os.makedirs(target_dir, exist_ok=True)
    monkeypatch.setenv("AGENT_CONFIG_DIR", target_dir)

    # 1) Valid config
    write_file(os.path.join(target_dir, "good.yaml"),
        """
name: Good Bot
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

    # 2) Invalid YAML syntax -> parse error path
    write_file(os.path.join(target_dir, "invalid_yaml.yaml"),
        """
name: Bad YAML
llm:
  provider: openai
  model: gpt-4o-mini
workflow
  type: single_step
prompts:
  en: "Hello"
        """
    )

    # 3) Invalid schema (missing required keys) -> validator not ok
    write_file(os.path.join(target_dir, "bad_schema.yaml"),
        """
name: Missing Keys Bot
llm:
  provider: openai
  model: gpt-4o-mini
# missing workflow and prompts
        """
    )

    # 4) Build failure (wrong type for workflow)
    write_file(os.path.join(target_dir, "bad_build.yaml"),
        """
name: Wrong Type Bot
llm:
  provider: openai
  model: gpt-4o-mini
workflow: 123
prompts:
  en: "Hello"
        """
    )

    configs = load_agent_configs(dir_path=target_dir)
    # Only the valid config should be returned
    assert len(configs) == 1
    assert configs[0].name == "Good Bot"