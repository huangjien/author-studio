import pytest

from src.agents.autogen_adapter import _compose_task, run_single_turn
from src.core.models.agent import Agent


@pytest.fixture(autouse=True)
def enable_autogen_mock(monkeypatch):
    monkeypatch.setenv("AGENTS_AUTOGEN_MOCK", "1")
    yield
    monkeypatch.delenv("AGENTS_AUTOGEN_MOCK", raising=False)


def make_agent():
    return Agent(
        agent_id="alpha",
        llm_config={"model": "gpt-4o-mini", "provider": "openai"},
        workflow={},
        prompts={"en": "You are a helpful assistant."},
        tools=[],
        mcp_servers=[],
    )


def test_context_injection_on_first_turn_with_history():
    agent = make_agent()
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "agent", "content": "Hi, how can I help?"},
    ]
    result = run_single_turn(
        agent,
        "What's next?",
        accept_language="en",
        session_id="sess-1",
        session_history=history,
    )
    assert result["ok"] is True
    output = result["chat_result"]
    # Echo contains composed task; ensure context marker present
    assert "Conversation context" in output
    assert "- user: Hello" in output
    assert "Current request:" in output


def test_compose_task_handles_empty_history():
    # Directly test compose helper for robustness
    composed = _compose_task("Do X", history=None)
    assert composed == "Do X"


def test_multiple_turns_same_session_reuse_and_context_accumulates():
    agent = make_agent()
    session_id = "sess-2"

    # First turn with some history
    history1 = [
        {"role": "user", "content": "Prior question A"},
        {"role": "agent", "content": "Answer A"},
    ]
    res1 = run_single_turn(
        agent,
        "New question B",
        accept_language="en",
        session_id=session_id,
        session_history=history1,
    )
    assert res1["ok"] is True
    assert "Answer A" in res1["chat_result"]

    # Second turn with updated history should still include prior transcript
    history2 = history1 + [{"role": "user", "content": "Follow-up C"}]
    res2 = run_single_turn(
        agent,
        "Final question D",
        accept_language="en",
        session_id=session_id,
        session_history=history2,
    )
    assert res2["ok"] is True
    echo2 = res2["chat_result"]
    assert "Prior question A" in echo2
    assert "Follow-up C" in echo2
