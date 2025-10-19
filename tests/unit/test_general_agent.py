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


def test_detect_tool_request_fetch_url_prefer_http():
    agent = make_agent_with_tools(tools=["fetch"])  # supports fetch directly
    ga = GeneralAgent(agent)
    text = "Please fetch https://example.com (prefer http)"
    selection = ga.detect_tool_request(text)
    assert selection is not None
    name, args = selection
    assert name == "fetch"
    assert args["url"].startswith("https://example.com")
    assert args.get("prefer") == "http"


def test_detect_tool_request_search_top():
    agent = make_agent_with_tools(
        tools=[],
        mcp_servers=[{"name": "local-web-search", "type": "local", "tools": ["web_search"]}],
    )
    ga = GeneralAgent(agent)
    text = "Search python pytest top 3"
    selection = ga.detect_tool_request(text)
    assert selection is not None
    name, args = selection
    assert name == "web_search"
    assert args["query"] == text
    assert args.get("top_n") == 3


def test_detect_tool_request_none_when_no_support():
    agent = make_agent_with_tools(tools=[], mcp_servers=[])
    ga = GeneralAgent(agent)
    assert ga.detect_tool_request("Just echo this, please.") is None


def test_sanitize_url_strips_wrappers_and_punctuation():
    ga = GeneralAgent(make_agent_with_tools(tools=["fetch"]))
    raw = "'(`https://example.com/path,)'"
    cleaned = ga._sanitize_url(raw)
    assert cleaned == "https://example.com/path"


def test_detect_tool_request_prefer_process():
    agent = make_agent_with_tools(tools=["fetch"])  # supports fetch directly
    ga = GeneralAgent(agent)
    text = "Go to https://example.com via process"
    selection = ga.detect_tool_request(text)
    assert selection is not None
    name, args = selection
    assert name == "fetch"
    assert args["url"] == "https://example.com"
    assert args.get("prefer") == "process"


def test_supports_tool_handles_exception_gracefully():
    class BadAgent:
        def __getattr__(self, name):  # simulate attribute access error
            raise RuntimeError("bad agent")

    ga = GeneralAgent(BadAgent())
    assert ga.supports_tool("web_search") is False
