import os
import sys

import pytest

# Ensure repository root is on sys.path for 'src' package imports
REPO_ROOT = os.path.dirname(os.path.abspath(os.path.join(__file__, os.pardir)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Global AutoGen stub to make /agents/{agent_id}/invoke deterministic in tests
# Tests can override this stub locally using monkeypatch as needed.


@pytest.fixture(autouse=True)
def stub_autogen_in_agents_route(monkeypatch):
    try:
        import src.api.routes.agents as routes

        # Force AutoGen availability
        monkeypatch.setattr(routes, "autogen_available", lambda: True, raising=True)
        monkeypatch.setattr(routes, "autogen_supports_async", lambda: True, raising=True)

        async def fake_run_single_turn_async(
            agent, user_input, accept_language=None, session_id=None, session_history=None
        ):
            return {"ok": True, "chat_result": f"Echo: {user_input} (agent={agent.agent_id})"}

        def fake_run_single_turn(
            agent, user_input, accept_language=None, session_id=None, session_history=None
        ):
            return {"ok": True, "chat_result": f"Echo: {user_input} (agent={agent.agent_id})"}

        monkeypatch.setattr(
            routes, "run_single_turn_async", fake_run_single_turn_async, raising=True
        )
        monkeypatch.setattr(routes, "run_single_turn", fake_run_single_turn, raising=True)
    except Exception:
        # If routes cannot be imported yet (rare), skip; individual tests can patch manually.
        pass
