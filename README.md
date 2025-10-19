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

## Docker Compose
A ready-to-use `docker-compose.yml` is included. It defines:
- `app`: the FastAPI application built from `docker/studio.Dockerfile`
- `sqlite`: a helper container providing SQLite extensions and a shared volume
- `nginx`: a reverse proxy forwarding to `app` and exposing port 8080

Quick start:
```bash
# Build and start services
docker compose up --build -d

# Check app health (via nginx)
curl -s http://localhost:8080/health | jq

# Or app directly
curl -s http://localhost:8000/health | jq

# Tail logs
docker compose logs -f app

# Stop
docker compose down
```

Notes:
- The app service includes a healthcheck that probes `GET /health` internally.
- Nginx forwards `/health` and `/static/` to the app; general API requests are proxied to the app.
- Configure Ollama host and embed model via environment:
  - `OLLAMA_HOST` (default `http://host.docker.internal:11434` on macOS; ensure reachable)
  - `OLLAMA_EMBED_MODEL` (default `Qwen3-Embedding:latest`)
- Place an MCP servers config at repo root as `mcp_servers.json` (a sample is provided). The `/mcp/status` endpoint reports configured servers.

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

## Using AutoGen with /agents (Default)
The `/agents/{agent_id}/invoke` endpoint now delegates to the AutoGen adapter by default. This provides:
- Async, non-blocking single-turn execution using AgentChat 0.7.5
- Deterministic mock mode for tests and local dev
- Session persistence and localization identical to previous behavior

Install AutoGen:
```bash
pip install -U "autogen-agentchat==0.7.5" "autogen-ext[openai,mcp]==0.7.5"
# Or via project extras:
pip install .[autogen-stable]
```

Environment flags:
- `AGENTS_USE_AUTOGEN` (default `true`): enables AutoGen-only mode for `/agents/{agent_id}/invoke`.
  - If set to `false`, the endpoint responds with `501 Not Implemented`.
- `AGENTS_AUTOGEN_MOCK` (default `0`): when set to `1`, the AutoGen adapter returns a deterministic echo result.
  - Useful for Docker tests and offline local development without provider credentials.

Example request:
```bash
curl -s http://localhost:8000/agents/alpha-bot/invoke \
  -H "X-API-Key: $API_KEY" \
  -H "Accept-Language: en" \
  -H "Content-Type: application/json" \
  -d '{"input":"Hello from AutoGen"}' | jq
```
Response shape:
```json
{
  "agent_id": "alpha-bot",
  "session_id": "...",
  "output": "Echo: Hello from AutoGen (agent=alpha-bot)",
  "selected_language": "en"
}
```

Provider keys:
- Set `OPENAI_API_KEY` (or other providers as supported by your agents) in the environment when not using mock mode.
- Output content is model-dependent; tests only assert the presence of a string `output`.

MCP integration:
- The `autogen-stable` extra includes `autogen-ext[mcp]` to enable connecting to MCP servers.
- See `mcp_servers.json` and upcoming docs for configuring MCP tools.
