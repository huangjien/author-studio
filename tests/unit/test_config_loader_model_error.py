import importlib


def test_loader_skips_when_model_instantiation_fails(tmp_path):
    # Create config that passes validator but fails AgentConfig due to wrong 'tools' type
    cfg_dir = tmp_path / "agent_configs"
    cfg_dir.mkdir()
    bad = cfg_dir / "bad_tools.yaml"
    bad.write_text(
        """
name: good-agent
llm:
  provider: openai
workflow: {}
prompts:
  en: hello
# Wrong type: dict instead of list
tools:
  t1: should_be_a_list
        """
    )

    import src.config.loader as loader

    importlib.reload(loader)

    # Should log and skip the bad file, returning empty list
    configs = loader.load_agent_configs(str(cfg_dir))
    assert configs == []
