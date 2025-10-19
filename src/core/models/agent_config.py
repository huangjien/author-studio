from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class WorkflowConfig(BaseModel):
    type: Optional[str] = None
    human_in_loop: Optional[str] = None


class MCPServerConfig(BaseModel):
    name: str
    type: str  # 'local', 'http', or 'process'
    url: Optional[str] = None
    tools: Optional[List[str]] = None
    headers: Optional[Dict[str, str]] = None
    path_template: Optional[str] = None
    # Process-based MCP servers (e.g., stdio)
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    # Persistence and retry/timeouts for process servers
    persistent: Optional[bool] = True
    initialize_timeout: Optional[float] = 3.0
    call_timeout: Optional[float] = 5.0
    list_tools_timeout: Optional[float] = 3.0
    tool_call_retries: Optional[int] = 1
    retry_backoff_ms: Optional[int] = 250


class AgentConfig(BaseModel):
    name: str
    description: Optional[str] = None
    llm: Dict[str, Any]
    workflow: WorkflowConfig | Dict[str, Any] | None = None
    prompts: Optional[Dict[str, Any]] = None
    tools: Optional[List[str]] = None
    mcp_servers: Optional[List[MCPServerConfig]] = None
