import os
from fastapi.testclient import TestClient

API_KEY = "test-key"

def setup_env(tmp_dir):
    os.environ["API_KEY"] = API_KEY
    target_dir = os.path.join(tmp_dir, "agent_configs")
    os.environ["AGENT_CONFIG_DIR"] = target_dir
    os.makedirs(target_dir, exist_ok=True)
    with open(os.path.join(target_dir, "alpha.yaml"), "w") as f:
        f.write(
            """
            name: Alpha Bot
            llm:
              provider: openai
              model: gpt-4o-mini
            workflow:
              type: single_step
            prompts:
              en: "Hello"
            tools: []
            mcp_servers:
              - name: proc-fetch
                type: process
                tools: ["fetch", "web_search"]
                command: mcp-server-fetch
                persistent: true
            """
        )
    return target_dir


def main():
    tmp_dir = "/Users/huangjien/workspace/author-studio/tmp"
    os.makedirs(tmp_dir, exist_ok=True)
    setup_env(tmp_dir)

    import src.api.routes.agents as agents_routes
    # Force availability and async
    agents_routes.autogen_available = lambda: True
    agents_routes.autogen_supports_async = lambda: True
    directive = (
        'MCP_DIRECTIVE: {"tool": "web_search", "provider": "process", '
        '"arguments": {"query": "LangChain", "top_n": 1}}'
    )
    agents_routes.run_single_turn_async = lambda *a, **k: {
        "ok": True,
        "chat_result": f"Echo: test. {directive}",
        "session_selected_language": "en",
    }

    import src.services.mcp_manager as mcp_manager

    class FakeClient:
        def call_tool(self, name, args_dict, timeout=5.0):
            if name == "fetch":
                body = {
                    "query": {
                        "search": [
                            {"title": "LangChain", "snippet": "A framework for LLM apps."}
                        ]
                    }
                }
                import json as _json
                return {
                    "status": 200,
                    "body": _json.dumps(body),
                    "headers": {},
                    "url": args_dict.get("url", ""),
                }
            return {"status": 400, "body": "", "headers": {}, "url": ""}

    class FakeMgr:
        def acquire(self, *args, **kwargs):
            return FakeClient()
        def restart(self, *args, **kwargs):
            return FakeClient()

    mcp_manager.mcp_client_manager = FakeMgr()

    from src.main import app
    client = TestClient(app)
    resp = client.post(
        "/agents/alpha-bot/invoke",
        headers={"X-API-Key": API_KEY},
        json={"input": "Use web_search."},
    )
    print("status:", resp.status_code)
    try:
        print("json:", resp.json())
    except Exception:
        print("text:", resp.text)

if __name__ == "__main__":
    main()