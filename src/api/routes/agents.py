import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.agents.registry import AgentRegistry
from src.api.security import verify_api_key
from src.services import agent_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


class InvokeRequest(BaseModel):
    input: str
    session_id: Optional[str] = None


@router.post("/{agent_id}/invoke", dependencies=[Depends(verify_api_key)])
async def invoke(agent_id: str, request: Request, body: InvokeRequest):
    # Ensure agent exists
    registry = AgentRegistry()
    registry.reload()
    if not registry.get_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")

    # Accept-Language header
    language = request.headers.get("Accept-Language")

    try:
        logger.info("Invoke request received for agent '%s'", agent_id)
        result = agent_service.invoke_agent(agent_id, body.input, body.session_id, language)
        logger.info("Invoke request processed for agent '%s'", agent_id)
        return result
    except KeyError:
        raise HTTPException(status_code=404, detail="Agent not found")
    except Exception as e:
        logger.exception("Error invoking agent '%s': %s", agent_id, e)
        raise HTTPException(status_code=500, detail="Internal Server Error")
