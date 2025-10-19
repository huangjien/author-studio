from src.agents import autogen_adapter
from src.agents.autogen_adapter import (
    _to_llm_config,
    is_available,
    run_single_turn,
    run_single_turn_async,
    supports_agentchat_async,
)
from src.core.models.agent import Agent


class RecClient:
    last_model = None

    def __init__(self, model: str):
        self.model = model
        RecClient.last_model = model


class RecAssistant:
    last_name = None
    last_system_message = "__unset__"

    def __init__(self, name: str, model_client: RecClient, system_message: str | None = None):
        RecAssistant.last_name = name
        RecAssistant.last_system_message = system_message
        self.model_client = model_client

    async def run(self, task: str):
        # Return a simple string; adapter should propagate as str
        return f"ok: {task} [{self.model_client.model}]"


class ObjResult:
    def __str__(self) -> str:
        return "STR_OBJ"


class RecAssistantObj:
    def __init__(self, name: str, model_client: RecClient, system_message: str | None = None):
        self.model_client = model_client

    async def run(self, task: str):
        # Return an object to validate str(result) behavior
        return ObjResult()


def test_is_available_true_when_import_stubbed(monkeypatch):
    monkeypatch.setattr(
        autogen_adapter,
        "_import_agentchat",
        lambda: {
            "AssistantAgent": RecAssistant,
            "OpenAIChatCompletionClient": RecClient,
        },
    )
    assert is_available() is True


def test_is_available_false_when_import_returns_none(monkeypatch):
    monkeypatch.setattr(autogen_adapter, "_import_agentchat", lambda: None)
    assert is_available() is False


def test_supports_agentchat_async_false_when_missing(monkeypatch):
    monkeypatch.setattr(autogen_adapter, "_import_agentchat", lambda: None)
    assert supports_agentchat_async() is False


def test_run_single_turn_async_error_when_missing_agentchat(monkeypatch):
    import asyncio

    monkeypatch.setattr(autogen_adapter, "_import_agentchat", lambda: None)
    agent = Agent(
        agent_id="missing",
        llm_config={"provider": "openai"},
        workflow={},
        prompts={},
        tools=[],
        mcp_servers=[],
    )
    result = asyncio.run(run_single_turn_async(agent, "hello"))
    assert result["ok"] is False
    assert "AgentChat 0.7.5 is not installed" in result.get("error", "")
    assert result.get("flavor") == "agentchat-0.7.5"


def test_to_llm_config_none_returns_empty_dict():
    assert _to_llm_config(None) == {}


def test_run_single_turn_wires_default_model_and_name_no_system(monkeypatch):
    monkeypatch.setattr(
        autogen_adapter,
        "_import_agentchat",
        lambda: {
            "AssistantAgent": RecAssistant,
            "OpenAIChatCompletionClient": RecClient,
        },
    )

    agent = Agent(
        agent_id="alpha",
        llm_config={"provider": "openai"},  # no model -> should default
        workflow={},
        prompts={},  # no system message
        tools=[],
        mcp_servers=[],
    )

    result = run_single_turn(agent, "do it")
    assert result["ok"] is True
    assert RecClient.last_model == "gpt-4o-mini"
    assert RecAssistant.last_name == "assistant_alpha"
    assert RecAssistant.last_system_message is None
    assert isinstance(result["chat_result"], str)


def test_run_single_turn_passes_system_message_from_workflow(monkeypatch):
    monkeypatch.setattr(
        autogen_adapter,
        "_import_agentchat",
        lambda: {
            "AssistantAgent": RecAssistant,
            "OpenAIChatCompletionClient": RecClient,
        },
    )

    agent = Agent(
        agent_id="alpha",
        llm_config={"model": "m1"},
        workflow={"system_message": "  Hello System  "},
        prompts={"system": "ignored"},
        tools=[],
        mcp_servers=[],
    )

    result = run_single_turn(agent, "do it")
    assert result["ok"] is True
    assert RecAssistant.last_system_message == "Hello System"


def test_run_single_turn_async_passes_system_message_from_prompts(monkeypatch):
    import asyncio

    monkeypatch.setattr(
        autogen_adapter,
        "_import_agentchat",
        lambda: {
            "AssistantAgent": RecAssistant,
            "OpenAIChatCompletionClient": RecClient,
        },
    )

    agent = Agent(
        agent_id="beta",
        llm_config={"model": "m2"},
        workflow={},
        prompts={"system": "  From Prompts  "},
        tools=[],
        mcp_servers=[],
    )

    result = asyncio.run(run_single_turn_async(agent, "async"))
    assert result["ok"] is True
    assert RecAssistant.last_system_message == "From Prompts"


def test_run_single_turn_chat_result_is_string_when_object_returned(monkeypatch):
    monkeypatch.setattr(
        autogen_adapter,
        "_import_agentchat",
        lambda: {
            "AssistantAgent": RecAssistantObj,
            "OpenAIChatCompletionClient": RecClient,
        },
    )

    agent = Agent(
        agent_id="gamma",
        llm_config={"model": "m3"},
        workflow={},
        prompts={},
        tools=[],
        mcp_servers=[],
    )

    result = run_single_turn(agent, "obj")
    assert result["ok"] is True
    assert result["chat_result"] == "STR_OBJ"


def test_run_single_turn_missing_agentchat_flavor_constant(monkeypatch):
    monkeypatch.setattr(autogen_adapter, "_import_agentchat", lambda: None)

    agent = Agent(
        agent_id="delta",
        llm_config={"model": "m4"},
        workflow={},
        prompts={},
        tools=[],
        mcp_servers=[],
    )

    result = run_single_turn(agent, "missing")
    assert result["ok"] is False
    assert result.get("flavor") == "agentchat-0.7.5"
