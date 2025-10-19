from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

# AutoGen adapter imports for preferred invocation path
from src.agents.autogen_adapter import is_available as autogen_available
from src.agents.autogen_adapter import run_single_turn, run_single_turn_async
from src.agents.autogen_adapter import supports_agentchat_async as autogen_supports_async
from src.agents.registry import AgentRegistry
from src.api.security import verify_api_key
from src.config.env import settings
from src.core.i18n import get_localized_prompt
from src.services.session_service import session_service

# from src.services import agent_service  # Removed legacy import, AutoGen-only path now
from src.services.tool_service import ToolService

router = APIRouter()
registry = AgentRegistry()


class InvokeRequest(BaseModel):
    input: str
    session_id: Optional[str] = None


class ToolInvokeRequest(BaseModel):
    arguments: Optional[Dict[str, Any]] = None


@router.get("/agents")
async def list_agents():
    registry.reload(dir_path=settings.agent_config_dir)
    return registry.list_agents()


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    registry.reload(dir_path=settings.agent_config_dir)
    agent = registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent


@router.get("/agents/{agent_id}/tools")
async def list_agent_tools(agent_id: str):
    registry.reload(dir_path=settings.agent_config_dir)
    agent = registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    try:
        service = ToolService()
        result = service.list_tools(agent_id)
        return result
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@router.post("/agents/{agent_id}/invoke", dependencies=[Depends(verify_api_key)])
async def invoke(
    agent_id: str,
    request: Request,
    body: InvokeRequest,
    accept_language: Optional[str] = Header(None),
):
    # AutoGen-only path: use AutoGen adapter and fail if unavailable
    try:
        language = accept_language
        registry.reload(dir_path=settings.agent_config_dir)
        agent = registry.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

        # Enforce AutoGen-only mode based on feature flag; if disabled, return 501
        if not settings.agents_use_autogen:
            raise HTTPException(
                status_code=501,
                detail=(
                    "AutoGen-only mode is disabled (AGENTS_USE_AUTOGEN=false). \
                    Enable it to use /agents invoke."
                ),
            )

        # Require AutoGen to be installed; if not available, raise 501 Not Implemented
        if not autogen_available():
            raise HTTPException(
                status_code=501,
                detail=(
                    "AutoGen AgentChat 0.7.5 is not installed. \
                    Install with `pip install .[autogen-stable]` "
                    'or `pip install "autogen-agentchat==0.7.5" \
                    "autogen-ext[openai,mcp]==0.7.5"`.'
                ),
            )

        # Create or continue session (preserve session behavior and persistence)
        if body.session_id:
            session = session_service.continue_session(
                body.session_id
            ) or session_service.create_session(agent_id)
        else:
            session = session_service.create_session(agent_id)

        # Run AutoGen using async path if supported
        try:
            if autogen_supports_async():
                result = await run_single_turn_async(
                    agent,
                    body.input,
                    language,
                    session_id=session.session_id,
                    session_history=session.history,
                )
            else:
                result = run_single_turn(
                    agent,
                    body.input,
                    language,
                    session_id=session.session_id,
                    session_history=session.history,
                )

            if not result.get("ok"):
                # AutoGen responded with an error; propagate as 500
                raise RuntimeError(result.get("error") or "AutoGen error")

            # Use session-selected language if adapter provided one; otherwise localized fallback
            sess_lang = result.get("session_selected_language")
            if isinstance(sess_lang, str) and sess_lang:
                selected_lang = sess_lang
                prompt_text = (agent.prompts or {}).get(sess_lang) or None
            else:
                selected_lang, prompt_text = get_localized_prompt(agent.prompts or {}, language)

            output_text = str(result.get("chat_result"))

            # Update session history and persist
            session.history.append(
                {"role": "user", "content": body.input, "language": language or selected_lang}
            )
            session.history.append(
                {"role": "agent", "content": output_text, "language": selected_lang}
            )
            session_service._persist(session)

            return {
                "agent_id": agent.agent_id,
                "session_id": session.session_id,
                "output": output_text,
                "selected_language": selected_lang,
            }
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=str(e))
    except HTTPException as e:
        raise e
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


# Minimal MCP-compatible endpoint to proxy tool invocation directly.
# This avoids recursion when ToolService needs a remote HTTP endpoint.
@router.post("/mcp/tools/{tool_name}")
async def mcp_tool_proxy(tool_name: str, req: ToolInvokeRequest):
    try:
        args = req.arguments or {}
        if tool_name == "web_search":
            from src.tools.providers.local_web_search import web_search

            query = args.get("query") or args.get("q") or ""
            top_n = int(args.get("top_n", 5))
            return web_search(query=query, top_n=top_n)
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    except HTTPException as e:
        # Propagate expected HTTP errors (e.g., 404) unchanged
        raise e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
