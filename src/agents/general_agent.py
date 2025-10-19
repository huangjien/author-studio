import re
from typing import Optional

from src.core.models.agent import Agent


class GeneralAgent:
    """General-purpose helper for intent detection and tool selection.

    Encapsulates minimal logic to:
    - Detect URL fetch intent
    - Detect search intent
    - Prefer transport types based on hints in the text (local/http/process)
    """

    def __init__(self, agent: Agent):
        self.agent = agent

    def supports_tool(self, tool_name: str) -> bool:
        try:
            tools = self.agent.tools or []
            server_tools = []
            for s in self.agent.mcp_servers or []:
                server_tools.extend(s.get("tools") or [])
            return tool_name in tools or tool_name in server_tools
        except Exception:
            return False

    @staticmethod
    def _sanitize_url(u: str) -> str:
        if not isinstance(u, str):
            return ""
        u = u.strip()
        # Strip common trailing punctuation/wrappers
        u = re.sub(r'[`"\'()\[\]<>.,;]+$', "", u)
        # Strip common leading wrappers
        u = re.sub(r'^[\'"`(<\[]+', "", u)
        return u

    def detect_tool_request(self, text: str):
        lower = (text or "").lower()
        prefer: Optional[str] = None
        if "prefer http" in lower or "via http" in lower:
            prefer = "http"
        elif "prefer process" in lower or "via process" in lower or "via stdio" in lower:
            prefer = "process"
        elif "prefer local" in lower:
            prefer = "local"

        # URL detection -> fetch
        url_match = re.search(r"(https?://[^\s]+)", text or "")
        if url_match and self.supports_tool("fetch"):
            raw_url = url_match.group(1)
            args = {"url": self._sanitize_url(raw_url)}
            if prefer:
                args["prefer"] = prefer
            return ("fetch", args)

        # Search intent -> web_search
        search_triggers = [
            "search",
            "find",
            "look up",
            "lookup",
            "google",
            "bing",
            "duckduckgo",
            "wikipedia",
            "wiki",
            "who is",
            "what is",
        ]
        if any(t in lower for t in search_triggers) and self.supports_tool("web_search"):
            args = {"query": text}
            top_match = re.search(r"\btop\s+(\d+)", lower)
            if top_match:
                try:
                    args["top_n"] = int(top_match.group(1))
                except Exception:
                    pass
            if prefer:
                args["prefer"] = prefer
            return ("web_search", args)

        return None
