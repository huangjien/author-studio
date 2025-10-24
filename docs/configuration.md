# Configuration

This document lists environment variables and recommended defaults for the AI Agent Hosting application, including multi-turn session behavior and the AutoGen adapter.

Overview
- Configuration is typically supplied via a `.env` file loaded by Docker (see `make docker-run`) or your shell environment.
- The `/agents/{agent_id}/invoke` route supports AutoGen mode, session continuity, i18n, and context window controls.

Required
- API_KEY: The server-side API key expected in the `X-API-Key` header for protected endpoints.

Agent runtime
- AGENTS_USE_AUTOGEN (default `true`): Enables AutoGen-only mode for `/agents/{agent_id}/invoke`.
  - If set to `false`, the endpoint responds with `501 Not Implemented`.
- AGENTS_AUTOGEN_MOCK (default `0`): When set to `1`, the AutoGen adapter returns a deterministic echo result.
  - Useful for Docker tests and offline local development without provider credentials.

Session context controls
- AGENTS_AUTOGEN_CONTEXT_MAX_MESSAGES (default `8`): Number of recent session messages to include in the context block prepended to the current request.
- AGENTS_AUTOGEN_CONTEXT_MAX_CHARS (default `500`): Maximum characters per message included in the context block.

Session lifecycle controls
- AGENTS_AUTOGEN_SESSION_TTL_DAYS (default `30`): In-memory session agent registry TTL. Expired sessions are pruned automatically.
- AGENTS_AUTOGEN_SESSION_TTL_SECONDS (optional): Fine-grained TTL override; if set, it takes precedence over the day-based setting.

Language consistency
- For a given `session_id`, the language selected on the first turn (or provided via `workflow.system_message`) is reused on subsequent turns.
- Mid-session `Accept-Language` values will not override the session’s language. The adapter returns `session_selected_language` and the route uses it to update session history and response metadata.

Provider credentials (optional)
- Set provider-specific keys in your environment when not using mock mode (examples: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.). Your agent configs determine which providers are needed.

Example .env
```
# Core API key for protected endpoints
API_KEY=your-secret-api-key

# Agent runtime
AGENTS_USE_AUTOGEN=true
AGENTS_AUTOGEN_MOCK=0

# Session context
AGENTS_AUTOGEN_CONTEXT_MAX_MESSAGES=8
AGENTS_AUTOGEN_CONTEXT_MAX_CHARS=500

# Session lifecycle (30 days default)
AGENTS_AUTOGEN_SESSION_TTL_DAYS=30
# Optional fine-grained TTL override (takes precedence if set)
# AGENTS_AUTOGEN_SESSION_TTL_SECONDS=2592000

# Provider keys (optional)
# OPENAI_API_KEY=sk-xxxx
# ANTHROPIC_API_KEY=sk-xxxx
# GROQ_API_KEY=sk-xxxx
```

MCP integration
- Agents can declare MCP servers via `mcp_servers` in their YAML (see `agent_configs/alpha.yaml`).
- A sample `mcp_servers.json` is included at repo root; the `/mcp/status` endpoint reports configured servers.
- The `/agents/{agent_id}/invoke` endpoint supports directive-driven tool routing when the LLM emits an `MCP_DIRECTIVE:` JSON.
- Tool execution results are wrapped with metadata in responses:
  - `provider`: `process`, `http`, or `local`
  - `server`: server name
  - `data`: tool-specific payload

Example curl
```bash
curl -sS -X POST http://localhost:8000/agents/alpha-bot/invoke \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $(tail -n 1 keys.txt)" \
  -d '{"input": "Search Wikipedia for LangChain, top 3. Emit MCP_DIRECTIVE with provider=process and tool=web_search."}' \
  | jq '{tool_used, tool_result: {provider: .tool_result.provider, server: .tool_result.server, has_data: (.tool_result.data != null)}}'
```