import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.agents.autogen_adapter import is_available as autogen_available
from src.agents.autogen_adapter import run_single_turn, run_single_turn_async
from src.agents.autogen_adapter import supports_agentchat_async as autogen_supports_async
from src.agents.registry import AgentRegistry
from src.api.security import verify_api_key
from src.config.env import settings

router = APIRouter()
registry = AgentRegistry()
logger = logging.getLogger(__name__)


class AutoGenInvokeRequest(BaseModel):
    input: str
    session_id: Optional[str] = None


@router.post("/autogen/{agent_id}/invoke", dependencies=[Depends(verify_api_key)])
async def autogen_invoke(agent_id: str, request: Request, body: AutoGenInvokeRequest):
    # Feature-flagged endpoint; disabled by default
    if not settings.autogen_enabled:
        raise HTTPException(status_code=404, detail="AutoGen endpoint is disabled")

    registry.reload(dir_path=settings.agent_config_dir)
    agent = registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    # Strict workflow gate: require explicit opt-in via workflow.type == 'autogen'
    workflow_type = (agent.workflow or {}).get("type", "").strip().lower()
    if workflow_type != "autogen":
        # Observability: record denied invocation due to workflow mismatch
        logger.warning(
            "autogen.invoke.denied_wrong_workflow",
            extra={
                "agent_id": agent_id,
                "workflow_type": workflow_type,
                "session_id": body.session_id,
                "path": request.url.path,
                "method": request.method,
            },
        )
        raise HTTPException(
            status_code=400, detail="Agent workflow must be 'autogen' to use this endpoint"
        )

    if not autogen_available():
        raise HTTPException(
            status_code=501,
            detail=(
                "AutoGen AgentChat 0.7.5 is not installed. "
                "Install with `pip install .[autogen-stable]`."
            ),
        )

    try:
        # Observability: record start of invocation
        logger.info(
            "autogen.invoke.start",
            extra={
                "agent_id": agent_id,
                "workflow_type": workflow_type,
                "session_id": body.session_id,
                "path": request.url.path,
                "method": request.method,
            },
        )

        # Prefer async AgentChat path when available to avoid asyncio.run in event loop
        if autogen_supports_async():
            result = await run_single_turn_async(agent, body.input)
        else:
            result = run_single_turn(agent, body.input)

        # Log the flavor used for observability with structured extras
        flavor = result.get("flavor") or "agentchat-0.7.5"
        logger.info(
            "autogen.invoke.success",
            extra={
                "agent_id": agent_id,
                "workflow_type": workflow_type,
                "session_id": body.session_id,
                "path": request.url.path,
                "method": request.method,
                "flavor": flavor,
            },
        )

        if result.get("ok"):
            # Return the adapter's structured result directly
            return result
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown AutoGen error"))
    except HTTPException:
        # Pass-through FastAPI errors
        raise
    except Exception as e:  # noqa: BLE001
        # Observability: record unexpected exception
        logger.error(
            "autogen.invoke.error",
            extra={
                "agent_id": agent_id,
                "workflow_type": workflow_type,
                "session_id": body.session_id,
                "path": request.url.path,
                "method": request.method,
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))
