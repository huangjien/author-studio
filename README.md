# AI Agent Hosting Application

A minimal, test-driven FastAPI application for hosting YAML-defined "agents" with:
- Agent configs stored as YAML in `agent_configs/`
- A simple invoke endpoint that echoes input and demonstrates localization, sessions, and caching
- File-based (and stubbed SQLite) persistence for session history
- API key security via the `X-API-Key` header

This repository is intentionally simple so you can layer in real LLM providers later.

## Requirements
- Python 3.13+ (developed against 3.13; Makefile auto-falls back from 3.14 to 3.13 for dependency compatibility)
- Dependencies: see `requirements.txt` (FastAPI, Uvicorn, PyYAML, Pydantic v2, etc.)
- Optional: `pytest-cov` for coverage, `python-dotenv` if you want to auto-load `.env`

## Project Structure
```
src/
  api/                 # FastAPI router(s) and API security
    routes/agents.py   # POST /agents/{agent_id}/invoke; POST /agents/{agent_id}/tools/{tool_name}
    security.py        # verify_api_key() from X-API-Key header
  agents/              # Agent registry and builder
    loader.py          # Build Agent from AgentConfig, slugify agent id
    registry.py        # Load, register, and list agents
  config/              # Config loader/validator and env settings
    env.py             # Settings read from environment vars
    loader.py          # Read YAML configs -> AgentConfig list
    validator.py       # Validates YAML dicts before model creation
  core/                # Core utilities and data models
    i18n.py            # Accept-Language parsing and prompt selection
    models/            # Pydantic models (Agent, AgentConfig, Session, etc.)
  services/            # Business logic
    agent_service.py   # invoke_agent(), compute_output() with caching
    session_service.py # create/continue sessions, persistence
    cache.py           # Simple LRU + memoize decorator
    persistence.py     # FileStore and SQLiteStore (minimal)
  main.py              # FastAPI app, /health endpoint, error handler
agent_configs/         # YAML definitions for agents
tests/                 # Unit, integration, and contract tests
```

## Quick Start
1. (Optional) Create and fill `.env` at repo root (already added):
   ```
   # API keys (choose one or more sources)
   API_KEY=changeme
   API_KEYS=
   API_KEYS_FILE=
   API_KEYS_TTL=10

   AGENT_CONFIG_DIR=agent_configs
   PERSISTENCE_MODE=file
   DATA_DIR=.data

   # Provider keys (for future integrations)
   OPENAI_API_KEY=
   ANTHROPIC_API_KEY=
   GEMINI_API_KEY=
   AZURE_OPENAI_API_KEY=
   AZURE_OPENAI_ENDPOINT=
   MISTRAL_API_KEY=
   COHERE_API_KEY=
   TOGETHER_API_KEY=
   DEEPSEEK_API_KEY=
   ```
   Then either export them in your shell:
   ```bash
   export $(cat .env | xargs)
   ```
   Or install `python-dotenv` and add `load_dotenv()` on startup.

2. Setup environment (Python + venv + deps):
   ```bash
   make setup
   ```

3. Run the server:
   ```bash
   make run PORT=8000
   ```

4. Test the `/health` endpoint:
   - GET http://localhost:8000/health -> `{ "status": "ok" }`

## Developer commands
```bash
make test
make format
make lint
make docker-build
make docker-run PORT=8000
make docker-stop
make docker-clean
make ollama-check
```

## Security
- API key is enforced on the agents router via `src/api/security.py`.
- Supported key sources:
  - `API_KEY`: single key.
  - `API_KEYS`: comma-separated list (e.g., `alpha, beta , gamma`).
  - `API_KEYS_FILE`: path to a file that can be updated at runtime.
    - File formats supported:
      - JSON object: `{ "keys": ["key1", "key2"] }`
      - JSON array: `["key1", "key2"]`
      - Newline-separated text:
        ```
        key1
        key2
        # blank lines and surrounding spaces are ignored
        ```
    - Changes are picked up automatically using a TTL cache.
  - `API_KEYS_TTL`: cache TTL in seconds (default `10`). Set to `0` to disable caching and reflect changes immediately.
- Invoke endpoint (`/agents/{agent_id}/invoke`) requires `X-API-Key: <your-key>` when keys are configured.
- Tools endpoint (`/agents/{agent_id}/tools/{tool_name}`) currently does NOT require API keys (tests rely on this); enable auth in production.
- If no keys are configured (all of the above unset/empty), requests are allowed (development convenience).

Example: dynamic keys file
```bash
# Create a keys file and point the app to it
printf "alpha\nbeta\n" > ./keys.txt
export API_KEYS_FILE=$(pwd)/keys.txt
export API_KEYS_TTL=10  # optional (default 10)

# Start the server (or container)
make run PORT=8000

# Later, rotate/add a key without restart
printf "gamma\n" > ./keys.txt
# Within ~10s the new key is accepted; set API_KEYS_TTL=0 for immediate picks
```

Docker example with file-based keys:
```bash
docker run -p 8000:8000 \
  -v $(pwd)/agent_configs:/app/agent_configs \
  -v $(pwd)/keys.txt:/app/keys.txt \
  -e API_KEYS_FILE=/app/keys.txt \
  ai-agent-app
```

## Agent Configuration
- Location: `agent_configs/` by default (override with `AGENT_CONFIG_DIR`).
- One YAML per agent. Minimal example:
  ```yaml
  name: Alpha Bot
  llm:
    provider: openai
    model: gpt-4o-mini
  workflow:
    type: single_step
  prompts:
    en: "Hello"
  tools: []
  ```
- The agent id is derived from `name` by slugifying (e.g., "Alpha Bot" -> `alpha-bot`).
- Duplicate ids are logged and skipped.
- Invalid YAMLs are logged and skipped.

### Example: Ollama + Qwen3:8b
An example agent config has been added:
`agent_configs/qwen3_8b.yaml`
```yaml
name: Qwen3 8B
llm:
  provider: ollama
  model: qwen3:8b
workflow:
  type: single_step
prompts:
  en: "You are Qwen3 8B running on Ollama. Reply concisely."
tools: []
```
To use it:
- Install and start Ollama.
- Pull the model: `ollama pull qwen3:8b`.
- The agent id will be `qwen3-8b`.

## API Reference
- `GET /health`
  - Returns environment-derived health information including:
    - `status`: always `"ok"` for static mode
    - `llm_providers`: map of provider => `{ configured, available, details }` based on environment variables (no network calls)
    - `agents`: list of registered agents with `{ agent_id, provider, model, languages, available }`
    - `agent_count`: total number of loaded agents
  - Optional live connectivity mode: `GET /health?live=true`
    - Performs lightweight connectivity checks to providers and returns:
      - `live`: `{ live_ok, results }`
      - Each `results[provider]` includes `{ ok, status_code, latency_ms, endpoint, error? }`
    - Restrict providers: `GET /health?live=true&providers=ollama,openai`
    - Control timeout: `GET /health?live=true&timeout_ms=2000`
  - Example static response:
    ```json
    {
      "status": "ok",
      "llm_providers": {
        "openai": { "configured": true, "available": true, "details": { "env": "OPENAI_API_KEY" } },
        "ollama": {
          "configured": true,
          "available": true,
          "details": {
            "env": "OLLAMA_HOST",
            "default_host": "http://localhost:11434",
            "resolved_host": "http://localhost:11434"
          }
        }
      },
      "agents": [
        {
          "agent_id": "alpha-bot",
          "provider": "openai",
          "model": "gpt-4o-mini",
          "languages": ["en", "es"],
          "available": true
        }
      ],
      "agent_count": 1
    }
    ```
  - Example live response (excerpt):
    ```json
    {
      "status": "ok",
      "llm_providers": { /* ... */ },
      "agents": [ /* ... */ ],
      "agent_count": 2,
      "live": {
        "live_ok": true,
        "results": {
          "ollama": { "ok": true, "status_code": 200, "latency_ms": 12.34, "endpoint": "http://localhost:11434/api/tags" },
          "openai": { "ok": true, "status_code": 200, "latency_ms": 123.45, "endpoint": "https://api.openai.com/v1/models" }
        }
      }
    }
    ```

- `POST /agents/{agent_id}/invoke`
  - Headers: `X-API-Key: <your-key>`
  - Optional header: `Accept-Language: <lang tags>` (e.g., `es-ES,es;q=0.9,en;q=0.8`)
  - Body:
    ```json
    { "input": "Hello", "session_id": "optional" }
    ```
  - Response (example):
    ```json
    {
      "agent_id": "alpha-bot",
      "session_id": "...",
      "output": "[alpha-bot] Echo: Hello",
      "selected_language": "en"
    }
    ```

## Localization (i18n)
- `Accept-Language` is parsed and matched against the agent's `prompts` keys.
- Fallbacks: tries exact match, base language (e.g., `es-ES` -> `es`), then `en`, then first available.

## Sessions & Persistence
- A session is created/continued during `invoke_agent()`.
- Minimal persistence:
  - File mode (default): JSON files under `DATA_DIR` (e.g., `.data/session_<id>.json`).
  - SQLite mode: initialized table, but persistence currently falls back to file (stubbed for future).
- Configure via env vars:
  - `PERSISTENCE_MODE=file|sqlite`
  - `DATA_DIR` (default `.data`)

## Caching
- `src/services/cache.py` implements a simple LRU cache.
- `compute_output()` is memoized for deterministic inputs.
- Cache key is built from function name, args, and kwargs; size defaults to 1024.

## Docker
- Build image:
  ```bash
  make docker-build
  ```
- Run container:
  ```bash
  make docker-run PORT=8000
  ```
- The `docker-run` target mounts `./agent_configs` into `/app/agent_configs`, loads `.env` automatically, and sets `AGENT_CONFIG_DIR=/app/agent_configs`. On Linux it uses host networking; on macOS/Windows it maps ports and uses `host.docker.internal` for Ollama.
- You can also pass provider keys via environment variables, e.g. `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, etc. In local dev, set them in `.env`.

## Testing & Coverage
- Run all tests:
  ```bash
  pytest -q
  ```
- Integration Docker tests are skipped unless you set:
  ```bash
  RUN_DOCKER_TESTS=1 pytest tests/integration/test_docker_build.py -q -rs
  RUN_DOCKER_TESTS=1 pytest tests/integration/test_docker_run.py -q -rs
  ```
- Coverage:
  ```bash
  pytest --cov=src --cov-report=term-missing
  pytest --cov=src --cov-report=html  # writes to htmlcov/index.html
  ```

## Extending: Real LLM Providers
- Today, `invoke_agent()` returns an echo response. To integrate real models:
  - Read provider API keys from environment (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).
  - Instantiate the client in `agent_service.py` based on agent `llm.provider` and `llm.model`.
  - Replace `compute_output()` with a call to the provider SDK.
- Keep secrets out of YAML files; use environment variables or your platform's secret store.

## Notes
- Duplicate agent ids (same slugified `name`) are skipped to prevent collisions.
- Invalid agent YAMLs (schema/type errors) are logged and skipped by the loader.
- The app includes a basic JSON error handler and logs for the invoke route.

## Screenshots
Place screenshots (PNG) under `docs/screenshots/` and they will be referenced here:

- Health endpoint
  
  ![Health endpoint](docs/screenshots/health.png)

- Invoke agent
  
  ![Invoke agent](docs/screenshots/invoke.png)

- Coverage report
  
  ![Coverage report](docs/screenshots/coverage.png)

Tips to generate:
- Start the server: `make run-env` (loads `.env` if present) or `make run`.
- Health: open `http://localhost:8000/health` in a browser or `curl -s http://localhost:8000/health | jq` and screenshot.
- Coverage: run `make cov-html`, then open `htmlcov/index.html` in your browser and screenshot the summary.

## Example curl commands

- Health check (static):
  ```bash
  curl -s http://localhost:8000/health | jq
  ```

- Health check (live connectivity):
  ```bash
  # Check all providers (Ollama always probed using resolved host; cloud providers probed only if configured)
  curl -s "http://localhost:8000/health?live=true" | jq

  # Restrict to specific providers
  curl -s "http://localhost:8000/health?live=true&providers=ollama,openai" | jq

  # Adjust timeout
  curl -s "http://localhost:8000/health?live=true&timeout_ms=500" | jq
  ```

- Invoke Alpha Bot with API key and language preference:
  ```bash
  curl -s -X POST http://localhost:8000/agents/alpha-bot/invoke \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${API_KEY:-changeme}" \
    -H "Accept-Language: es-ES,es;q=0.9,en;q=0.8" \
    -d '{"input": "Hola mundo"}' | jq
  ```

- Invoke Qwen3 8B (Ollama). Ensure `ollama pull qwen3:8b` and that Ollama is running. If calling from Docker, set `OLLAMA_HOST=http://host.docker.internal:11434`:
  ```bash
  curl -s -X POST http://localhost:8000/agents/qwen3-8b/invoke \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${API_KEY:-changeme}" \
    -d '{"input": "Hello"}' | jq
  ```

- Unknown agent (shows 404):
  ```bash
  curl -i -X POST http://localhost:8000/agents/does-not-exist/invoke \
    -H "Content-Type: application/json" \
    -H "X-API-Key: ${API_KEY:-changeme}" \
    -d '{"input": "test"}'
  ```

- Load environment from `.env` first:
  ```bash
  export $(cat .env | xargs)
  ```

## Makefile targets
A Makefile has been added with common tasks. Examples:

- Show available targets:
  ```bash
  make help
  ```
- Install deps:
  ```bash
  make install
  ```
- Run server (current shell env):
  ```bash
  make setup
  ```
  ```bash
  make run PORT=8000
  ```
- Run server loading `.env` if present:
  ```bash
  make run-env
```


- Tests and coverage:
  ```bash
  make test
  make test-verbose
  make cov
  make cov-html
  ```
- Docker build/run/stop:
  ```bash
  make docker-build
  make docker-run   # binds agent_configs and sets OLLAMA_HOST for Mac
  make docker-stop
  make docker-clean
  ```
- Formatting and linting:
  ```bash
  make format
  make lint
  ```

## Tools API
- POST /agents/{agent_id}/tools/{tool_name}
  - Headers: `Content-Type: application/json`
  - Auth: No API key required by default (tests). For production, protect this route.
  - Body:
    ```json
    { "arguments": { "query": "hello", "top_n": 2 } }
    ```
  - Example response:
    ```json
    {
      "tool": "web_search",
      "query": "hello",
      "results": [
        {
          "title": "Hello World - Wikipedia",
          "url": "https://example.org/hello",
          "snippet": "Hello World examples across languages."
        },
        {
          "title": "Greeting Etiquette",
          "url": "https://example.org/greetings",
          "snippet": "How to greet politely in many cultures."
        }
      ]
    }
    ```

- Behavior notes:
  - Registry reloads from `AGENT_CONFIG_DIR` on each tools request.
  - The local `web_search` tool is available even if the agent does not declare it.

## MCP-like Tool Providers

### Configure Alpha Bot for an HTTP MCP server
Add this to `agent_configs/alpha.yaml` (already configured by default):
```yaml
mcp_servers:
  - name: default-http
    type: http
    url: http://localhost:8012
    path_template: /mcp/tools/{tool_name}
    tools:
      - web_search
```
- `url`: base URL of the MCP server.
- `path_template`: remote path template. You can use `{tool_name}` and `{agent_id}`.
- `tools`: list of tool names provided by the server.

If the HTTP server is unreachable or returns an error, the app falls back to the local `web_search` provider to keep the system operational in development. In production, point `url` to your external MCP server and optionally add `headers` for auth:
```yaml
mcp_servers:
  - name: secure-http
    type: http
    url: https://mcp.example.com
    path_template: /api/tools/{tool_name}/invoke
    headers:
      Authorization: Bearer ${MCP_TOKEN}
    tools:
      - web_search
```
- Local provider: `web_search` returns deterministic offline results.
- Declare providers in agent YAML via `mcp_servers`:
  ```yaml
  name: Alpha Bot
  llm:
    provider: openai
    model: gpt-4o-mini
  workflow:
    type: single_step
  prompts:
    en: "Hello"
  tools: []
  mcp_servers:
    - name: default-local
      type: local
      tools:
        - web_search
  ```
- Tool resolution is handled by `ToolService`. For `type: http`, support will be added later.

### Process MCP servers (stdio client)
`ToolService` also supports `type: process` servers using a stdio-based MCP client. This lets you run tools via a local executable and optionally keep the process alive across requests.

- Example YAML:
  ```yaml
  mcp_servers:
    - name: fetcher
      type: process
      command: mcp-server-fetch
      args: ["--listen", "stdio"]
      env:
        EXAMPLE_TOKEN: ${EXAMPLE_TOKEN}
      tools:
        - fetch
        - web_search
      persistent: true            # keep process alive across requests
      initialize_timeout: 3.0     # seconds
      call_timeout: 5.0           # seconds
      list_tools_timeout: 2.0     # seconds (reserved)
      tool_call_retries: 1        # additional attempts on failure
      retry_backoff_ms: 250       # wait between retries (milliseconds)
  ```

- Behavior:
  - When `persistent: true`, `ToolService` acquires a client from a singleton manager (`MCPClientManager`) keyed by server name. The process is started once and reused.
  - On tool errors, `ToolService` will retry up to `tool_call_retries + 1` total attempts. Between attempts, it restarts the process via the manager and waits `retry_backoff_ms`.
  - When `persistent: false`, `ToolService` starts the process per request and stops it after the call (ephemeral mode). Retries are supported but without mid-call restarts.
  - If the process client fails, `web_search` falls back to the local provider for reliability.

- Supported tools:
  - `fetch`: perform an HTTP GET via the MCP server and return its raw response.
  - `web_search`: constructs a Wikipedia search URL, calls `fetch`, and returns a trimmed result list.

- Configuration model:
  - These fields are available on `MCPServerConfig` and flow through to `ToolService`:
    - `persistent`
    - `initialize_timeout`
    - `call_timeout`
    - `list_tools_timeout` (reserved)
    - `tool_call_retries`
    - `retry_backoff_ms`

### macOS setup notes (MCP subprocess servers)
If you use `type: process` with commands like `uvx mcp-server-fetch`, macOS may require a bit of extra setup:

- Install `uv` (provides `uvx`):
  - Homebrew: `brew install uv`
  - Official installer: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Ensure `uvx` is on your PATH (especially when launching from IDEs where PATH differs from your shell):
  ```bash
  which uvx
  export PATH="$HOME/.local/bin:$PATH"  # if uv installed to ~/.local/bin
  ```
- First run network prompts: The first time a subprocess makes outbound network calls (e.g., the `fetch` tool), macOS may show a firewall dialog like "Python wants to accept incoming connections" or "uv". Choose Allow.
- Python version: This repo targets Python 3.13 for widest compatibility. The Makefile auto-falls back from 3.14 to 3.13. If your system defaults to 3.14+, you can run:
  ```bash
  make setup  # will install 3.13 and create a virtualenv
  ```
  Or, with pyenv:
  ```bash
  pyenv local 3.13.0
  ```
- Absolute command path: If PATH issues persist, set `command` in YAML to an absolute path (e.g., `/opt/homebrew/bin/uvx` on Apple Silicon or `/usr/local/bin/uvx`), or avoid `uvx` and call the MCP binary directly if installed.
- Timeouts: On some macOS setups, process startup can be slower. Increase `initialize_timeout`, `list_tools_timeout`, or `call_timeout` if you see timeouts.

### HTTP MCP servers (example stub)
This explicit example shows how you can configure and implement a simple HTTP MCP provider. Note: `type: http` routing in `ToolService` is planned but not yet wired; calls will currently fall back to the local `web_search` in development.

- Agent YAML configuration:
  ```yaml
  mcp_servers:
    - name: example-http
      type: http
      url: http://localhost:8012
      path_template: /mcp/tools/{tool_name}
      tools:
        - web_search
        - fetch
      # Optional auth headers
      # headers:
      #   Authorization: Bearer ${MCP_TOKEN}
  ```

- Minimal HTTP MCP server (FastAPI):
  ```python
  # server.py
  from fastapi import FastAPI
  from pydantic import BaseModel
  from typing import Dict, Any, List

  app = FastAPI()

  class ToolCall(BaseModel):
      arguments: Dict[str, Any] = {}

  @app.post("/mcp/tools/fetch")
  def fetch(call: ToolCall):
      url = call.arguments.get("url", "https://example.org")
      # In a real implementation you would perform an HTTP GET here
      return {"tool": "fetch", "url": url, "status": 200, "body": "Example body ..."}

  @app.post("/mcp/tools/web_search")
  def web_search(call: ToolCall):
      q = call.arguments.get("query", "")
      top_n = int(call.arguments.get("top_n", 3))
      results: List[Dict[str, str]] = [
          {"title": "Hello World - Wikipedia", "url": "https://example.org/hello", "snippet": "Hello World examples across languages."},
          {"title": "Greeting Etiquette", "url": "https://example.org/greetings", "snippet": "How to greet politely in many cultures."},
          {"title": "Search Tips", "url": "https://example.org/tips", "snippet": "How to search effectively."},
      ]
      return {"tool": "web_search", "query": q, "results": results[:top_n]}
  ```

- Run the stub locally:
  ```bash
  uvicorn server:app --port 8012
  ```

- Test the stub directly:
  ```bash
  curl -s -X POST http://localhost:8012/mcp/tools/web_search \
    -H "Content-Type: application/json" \
    -d '{"arguments":{"query":"hello","top_n":2}}' | jq
  ```

- Contract notes:
  - `ToolService` will POST JSON with at least `{ "arguments": { ... } }`.
  - `path_template` supports `{tool_name}`; `{agent_id}` may be added later if needed.
  - For protected servers, include a `headers` block in YAML (e.g., `Authorization`).

- Current status:
  - The HTTP provider path is planned; until it's wired, `ToolService` falls back to the local `web_search` to keep development reliable.

### Auto-routing across MCP servers
- The ToolService will automatically select among MCP servers declared on the agent that advertise the requested tool.
- Default behavior for web_search: process > http > local. For fetch: process > http.
- You can influence ordering via:
  - priority in YAML: high > medium > low. Example:
    - Process server (Fetch): priority: high
    - HTTP server (HTTP Search): priority: low
  - prefer hint in request arguments:
    - prefer: "http" to favor HTTP
    - prefer: "process" or "stdio" to favor subprocess MCP
    - prefer: "local" to favor deterministic local provider
- Content hints: web_search queries containing "wikipedia" slightly favor process MCP (since our process MCP bridges to Wikipedia API via fetch).
- Candidates must list the tool in server.tools; otherwise, the server is ignored for that tool.

#### Agent-driven invocation
You do not need to call tool-specific endpoints. POST `/agents/{agent_id}/invoke` with natural-language input; the agent detects search (`web_search`) and URL-based fetch (`fetch`) if those tools are configured on the agent.

- You can nudge server selection by including phrases in the text:
  - "prefer http", "prefer process" (or "via stdio"), "prefer local"
- Responses include `output` and, when applicable, `tool_used` and `tool_result`.

Example:
```bash
curl -sS -X POST http://localhost:8000/agents/alpha-bot/invoke \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: YOUR_KEY' \
  -d '{"input":"Search Wikipedia for Ada Lovelace (prefer http)"}'
```

Examples
- Favor HTTP server:
  curl -sS -X POST http://localhost:8000/agents/alpha-bot/tools/web_search \
    -H 'Content-Type: application/json' \
    -d '{"arguments": {"query": "spaceX news", "top_n": 3, "prefer": "http"}}'
- Favor local deterministic stub:
  curl -sS -X POST http://localhost:8000/agents/alpha-bot/tools/web_search \
    -H 'Content-Type: application/json' \
    -d '{"arguments": {"query": "offline demo", "top_n": 3, "prefer": "local"}}'

## Example: Tools curl
```bash
curl -s -X POST http://localhost:8000/agents/alpha-bot/tools/web_search \
  -H "Content-Type: application/json" \
  -d '{"arguments":{"query":"hello","top_n":2}}' | jq
```

Unknown agent (404):
```bash
curl -i -X POST http://localhost:8000/agents/does-not-exist/tools/web_search \
  -H "Content-Type: application/json" \
  -d '{"arguments":{"query":"hello"}}'
```