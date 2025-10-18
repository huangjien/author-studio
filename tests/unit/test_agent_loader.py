from src.core.models.agent_config import AgentConfig, WorkflowConfig
from src.agents.loader import build_agent


def test_build_agent_creates_expected_agent_id_and_fields():
    cfg = AgentConfig(
        name="Alpha Bot",
        llm={"provider": "openai", "model": "gpt-4o-mini"},
        workflow={"type": "single_step", "human_in_loop": "optional"},
        prompts={"en": "Hello", "es": "Hola"},
        tools=["web_search"],
    )

    agent = build_agent(cfg)

    assert agent.agent_id == "alpha-bot"
    assert agent.llm_config == {"provider": "openai", "model": "gpt-4o-mini"}
    assert agent.workflow == {"type": "single_step", "human_in_loop": "optional"}
    assert agent.prompts == {"en": "Hello", "es": "Hola"}
    assert agent.tools == ["web_search"]


def test_build_agent_normalizes_workflow_model_to_dict():
    cfg = AgentConfig(
        name="Beta Bot",
        llm={"provider": "anthropic", "model": "claude-3-haiku"},
        workflow=WorkflowConfig(type="chain", human_in_loop="always"),
        prompts={"en": "Hi"},
        tools=[],
    )

    agent = build_agent(cfg)

    assert agent.agent_id == "beta-bot"
    assert agent.workflow == {"type": "chain", "human_in_loop": "always"}