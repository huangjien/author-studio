from src.agents import autogen_adapter
from src.agents.autogen_adapter import (
    _extract_system_message,
    _to_llm_config,
    run_single_turn,
    run_single_turn_async,
    supports_agentchat_async,
)
from src.core.models.agent import Agent


class StubClient:
    def __init__(self, model: str):
        self.model = model


class StubAssistant:
    def __init__(self, name: str, model_client: StubClient, system_message: str | None = None):
        self.name = name
        self.model_client = model_client
        self.system_message = system_message

    async def run(self, task: str):
        # Echo the task and model to validate wiring
        return f"stub-response: {task} [{self.model_client.model}]"


class FailingAssistant(StubAssistant):
    async def run(self, task: str):
        raise RuntimeError("simulated run failure")


def test_to_llm_config_pass_through_and_copy():
    src = {"model": "gpt-4o-mini", "provider": "openai", "extra": 123}
    out = _to_llm_config(src)
    assert out == src
    assert out is not src  # ensure a copy is returned


def test_extract_system_message_priority_workflow():
    agent = Agent(
        agent_id="a1",
        llm_config={"model": "gpt-4o-mini"},
        workflow={"system_message": "  Hello World  "},
        prompts={"system": "ignored", "en": "ignored"},
        tools=[],
        mcp_servers=[],
    )
    msg = _extract_system_message(agent)
    assert msg == "Hello World"


def test_extract_system_message_priority_prompts_system():
    agent = Agent(
        agent_id="a2",
        llm_config={"model": "gpt-4o-mini"},
        workflow={},
        prompts={"system": "System message", "en": "English"},
        tools=[],
        mcp_servers=[],
    )
    msg = _extract_system_message(agent)
    assert msg == "System message"


def test_extract_system_message_priority_prompts_en():
    agent = Agent(
        agent_id="a3",
        llm_config={"model": "gpt-4o-mini"},
        workflow={},
        prompts={"en": "English message", "other": "Other"},
        tools=[],
        mcp_servers=[],
    )
    msg = _extract_system_message(agent)
    assert msg == "English message"


def test_extract_system_message_fallback_first_prompt_value():
    # Dict preserves insertion order, so first value should be selected
    agent = Agent(
        agent_id="a4",
        llm_config={"model": "gpt-4o-mini"},
        workflow={},
        prompts={"first": "Pick me", "second": "Not me"},
        tools=[],
        mcp_servers=[],
    )
    msg = _extract_system_message(agent)
    assert msg == "Pick me"


def test_extract_system_message_none_when_no_prompts():
    agent = Agent(
        agent_id="a5",
        llm_config={"model": "gpt-4o-mini"},
        workflow={},
        prompts={},
        tools=[],
        mcp_servers=[],
    )
    msg = _extract_system_message(agent)
    assert msg is None


def test_run_single_turn_with_stubbed_agentchat(monkeypatch):
    # Stub AgentChat import to provide our test doubles
    monkeypatch.setattr(
        autogen_adapter,
        "_import_agentchat",
        lambda: {
            "AssistantAgent": StubAssistant,
            "OpenAIChatCompletionClient": StubClient,
        },
    )

    agent = Agent(
        agent_id="alpha",
        llm_config={"model": "stub-model", "provider": "openai"},
        workflow={},
        prompts={"system": "Hello from system"},
        tools=[],
        mcp_servers=[],
    )
    result = run_single_turn(agent, "Task text")
    assert result["ok"] is True
    assert result["agent_id"] == "alpha"
    assert result["input"] == "Task text"
    assert result["llm_config"]["model"] == "stub-model"
    assert result["flavor"] == "agentchat-0.7.5"
    assert "stub-response: Task text [stub-model]" in result["chat_result"]


def test_run_single_turn_async_with_stubbed_agentchat(monkeypatch):
    import asyncio

    monkeypatch.setattr(
        autogen_adapter,
        "_import_agentchat",
        lambda: {
            "AssistantAgent": StubAssistant,
            "OpenAIChatCompletionClient": StubClient,
        },
    )

    agent = Agent(
        agent_id="beta",
        llm_config={"model": "stub-model-2", "provider": "openai"},
        workflow={},
        prompts={"en": "Hello"},
        tools=[],
        mcp_servers=[],
    )
    result = asyncio.run(run_single_turn_async(agent, "Async task"))
    assert result["ok"] is True
    assert result["agent_id"] == "beta"
    assert result["llm_config"]["model"] == "stub-model-2"
    assert "stub-response: Async task [stub-model-2]" in result["chat_result"]


def test_supports_agentchat_async_true_when_import_stubbed(monkeypatch):
    monkeypatch.setattr(
        autogen_adapter,
        "_import_agentchat",
        lambda: {
            "AssistantAgent": StubAssistant,
            "OpenAIChatCompletionClient": StubClient,
        },
    )
    assert supports_agentchat_async() is True


def test_run_single_turn_error_path(monkeypatch):
    # Simulate a failure raised by AssistantAgent.run
    monkeypatch.setattr(
        autogen_adapter,
        "_import_agentchat",
        lambda: {
            "AssistantAgent": FailingAssistant,
            "OpenAIChatCompletionClient": StubClient,
        },
    )

    agent = Agent(
        agent_id="gamma",
        llm_config={"model": "stub-model-3", "provider": "openai"},
        workflow={},
        prompts={},
        tools=[],
        mcp_servers=[],
    )
    result = run_single_turn(agent, "Will fail")
    assert result["ok"] is False
    assert "autogen agentchat interaction failed" in result.get("error", "")
