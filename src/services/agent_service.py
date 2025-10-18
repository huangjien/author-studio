from typing import Optional

from src.agents.registry import AgentRegistry
from src.core.i18n import get_localized_prompt
from src.services.cache import memoize
from src.services.session_service import session_service

# For testing and observability of caching behavior
compute_output_call_count = 0


@memoize
def compute_output(
    agent_id: str,
    input_text: str,
    selected_lang: str,
    prompt_text: Optional[str],
) -> str:
    global compute_output_call_count
    compute_output_call_count += 1
    prefix = prompt_text or ""
    if prefix:
        return f"[{agent_id}] {prefix} :: Echo: {input_text}"
    else:
        return f"[{agent_id}] Echo: {input_text}"


def invoke_agent(
    agent_id: str,
    input_text: str,
    session_id: Optional[str] = None,
    language: Optional[str] = None,
) -> dict:
    """Minimal agent invocation for US2 & US4.
    - Looks up agent by id
    - Creates/continues a session
    - Chooses localized prompt based on Accept-Language (fallback to 'en')
    - Returns a simple echoed output with localized prefix
    """
    # Load registry from configured directory to find the agent
    registry = AgentRegistry()
    registry.reload()
    agent = registry.get_agent(agent_id)
    if not agent:
        raise KeyError(f"Agent '{agent_id}' not found")

    # Create/continue session
    if session_id:
        session = session_service.continue_session(session_id) or session_service.create_session(
            agent_id
        )
    else:
        session = session_service.create_session(agent_id)

    # Select localized prompt
    selected_lang, prompt_text = get_localized_prompt(agent.prompts or {}, language)

    # Compute output with caching based on agent_id, input_text, selected_lang, and prompt_text
    output = compute_output(agent.agent_id, input_text, selected_lang, prompt_text)

    # Update session history with language-aware content
    session.history.append(
        {"role": "user", "content": input_text, "language": language or selected_lang}
    )
    session.history.append({"role": "agent", "content": output, "language": selected_lang})

    # Persist minimal history update
    session_service._persist(session)

    return {
        "agent_id": agent.agent_id,
        "session_id": session.session_id,
        "output": output,
        "selected_language": selected_lang,
    }
