"""
Demonstration script for the optional AutoGen adapter.

Run:
    python scripts/run_autogen_demo.py "Your question here"

Requirements:
- AgentChat 0.7.5 installed: pip install -U "autogen-agentchat==0.7.5" "autogen-ext[openai,mcp]==0.7.5"
  or via project extras: pip install .[autogen-stable]
- Proper LLM credentials in environment (e.g., OPENAI_API_KEY) depending on your provider.

This script does not affect the main application or tests. It's a standalone demo.
"""
import sys

from src.core.models.agent import Agent
from src.agents.autogen_adapter import is_available, run_single_turn


def main():
    user_input = sys.argv[1] if len(sys.argv) > 1 else "Hello! Summarize AutoGen in one sentence."

    agent = Agent(
        agent_id="autogen-demo",
        llm_config={
            # Adjust to your provider/model. AgentChat passes through this config.
            "provider": "openai",
            "model": "gpt-4o-mini",
            # If needed, you can also include keys here. Prefer environment variables.
            # "api_key": os.getenv("OPENAI_API_KEY"),
        },
        workflow={},
        prompts={},
        tools=[],
        mcp_servers=[],
    )

    if not is_available():
        print("AutoGen AgentChat 0.7.5 is not installed. Install with `pip install .[autogen-stable]`.")
        sys.exit(1)

    result = run_single_turn(agent, user_input)
    if result.get("ok"):
        print("=== AutoGen Conversation Result ===")
        print(f"agent_id: {result['agent_id']}")
        print(f"input: {result['input']}")
        print("--- chat_result (string repr) ---")
        print(result["chat_result"])
    else:
        print("AutoGen conversation failed:")
        print(result.get("error"))
        sys.exit(2)


if __name__ == "__main__":
    main()
