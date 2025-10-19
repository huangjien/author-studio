from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.agents.registry import AgentRegistry
from src.api.security import verify_api_key
from src.config.env import settings
from src.services import agent_service
from src.services.tool_service import ToolNotFoundError, ToolService

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
async def invoke(agent_id: str, request: Request, body: InvokeRequest):
    try:
        language = request.headers.get("Accept-Language")
        result = agent_service.invoke_agent(
            agent_id=agent_id,
            input_text=body.input,
            session_id=body.session_id,
            language=language,
        )
        return result
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/tools/{tool_name}")
async def invoke_tool(agent_id: str, tool_name: str, req: ToolInvokeRequest):
    registry.reload(dir_path=settings.agent_config_dir)
    agent = registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    try:
        service = ToolService()
        result = service.invoke(
            agent_id=agent_id, tool_name=tool_name, arguments=req.arguments or {}
        )
        return result
    except ToolNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


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
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
