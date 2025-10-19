from src.agents.general_agent import GeneralAgent
from src.core.models.agent import Agent


def make_agent_with_tools(tools=None, mcp_servers=None):
    return Agent(
        agent_id="general",
        llm_config={"provider": "dummy"},
        workflow={},
        prompts={},
        tools=tools or [],
        mcp_servers=mcp_servers or [],
    )


def test_supports_tool_true_via_mcp_server():
    agent = make_agent_with_tools(
        tools=[],
        mcp_servers=[{"name": "local-search", "type": "local", "tools": ["web_search"]}],
    )
    ga = GeneralAgent(agent)
    assert ga.supports_tool("web_search") is True


def test_sanitize_url_non_string_returns_empty():
    ga = GeneralAgent(make_agent_with_tools())
    assert ga._sanitize_url(None) == ""


def test_fetch_priority_over_search_when_both_present():
    # Agent supports both fetch and web_search
    agent = make_agent_with_tools(
        tools=["fetch", "web_search"],
    )
    ga = GeneralAgent(agent)
    text = "search this https://example.com now"
    selection = ga.detect_tool_request(text)
    assert selection is not None
    name, args = selection
    assert name == "fetch"
    assert args["url"].startswith("https://example.com")


def test_search_trigger_variants():
    agent = make_agent_with_tools(
        tools=[],
        mcp_servers=[{"name": "local-search", "type": "local", "tools": ["web_search"]}],
    )
    ga = GeneralAgent(agent)
    variants = [
        "google python",
        "look up pytest",
        "who is Ada Lovelace",
    ]
    for text in variants:
        selection = ga.detect_tool_request(text)
        assert selection is not None
        name, args = selection
        assert name == "web_search"
        assert args["query"] == text


def test_prefer_local_applied_to_search():
    agent = make_agent_with_tools(
        tools=[],
        mcp_servers=[{"name": "local-search", "type": "local", "tools": ["web_search"]}],
    )
    ga = GeneralAgent(agent)
    text = "search python prefer local"
    selection = ga.detect_tool_request(text)
    assert selection is not None
    name, args = selection
    assert name == "web_search"
    assert args.get("prefer") == "local"


def test_top_n_non_integer_is_ignored():
    agent = make_agent_with_tools(
        tools=[],
        mcp_servers=[{"name": "local-search", "type": "local", "tools": ["web_search"]}],
    )
    ga = GeneralAgent(agent)
    text = "search testing top abc"
    selection = ga.detect_tool_request(text)
    assert selection is not None
    name, args = selection
    assert name == "web_search"
    assert "top_n" not in args


def test_via_stdio_sets_process_preference_for_search():
    agent = make_agent_with_tools(
        tools=[],
        mcp_servers=[{"name": "local-search", "type": "local", "tools": ["web_search"]}],
    )
    ga = GeneralAgent(agent)
    text = "lookup pytest via stdio"
    selection = ga.detect_tool_request(text)
    assert selection is not None
    name, args = selection
    assert name == "web_search"
    assert args.get("prefer") == "process"
