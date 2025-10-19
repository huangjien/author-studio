import os
from typing import Optional

from fastapi import APIRouter

from src.services.mcp_manager import mcp_client_manager

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/status")
def mcp_status(config_path: Optional[str] = None, ping: bool = False):
    """Return MCP servers status as configured in mcp_servers.json.

    Optionally accepts a config_path query param to point to a different file.
    """
    path = config_path or os.getenv("MCP_SERVERS_PATH", "mcp_servers.json")
    mcp_client_manager.load_servers_config(path)
    return {"servers": mcp_client_manager.get_status(ping=ping), "source": path}


# New endpoint: list all available MCP tools
@router.get("/tools")
def mcp_list_tools(config_path: Optional[str] = None, live: bool = True):
    """List available MCP tools across configured servers.

    Query params:
    - config_path: Optional path to the MCP servers config JSON file.
    - live: If True, query process-based servers for their tool list.
      Otherwise, use the configured 'tools' entries.
    """
    path = config_path or os.getenv("MCP_SERVERS_PATH", "mcp_servers.json")
    mcp_client_manager.load_servers_config(path)
    tools = mcp_client_manager.list_all_tools(query_live=live)
    return {"tools": tools, "source": path}
