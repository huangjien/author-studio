# Research: AI Agent Hosting Application

This document outlines the research and decisions made for the AI Agent Hosting Application.

## Research Topics

### 1. Structuring an AutoGen Application
- **Task**: Research best practices for structuring an AutoGen application with multiple configurable agents.
- **Findings**: AutoGen supports dynamic creation of agents. The best practice is to create a factory or manager class that is responsible for reading configuration files and instantiating `ConversableAgent` objects. This manager can hold a registry of all active agents, mapping an `agent_id` to the agent instance. This approach decouples the agent definition (config) from the application code.

### 2. Integrating FastAPI with AutoGen
- **Task**: Research patterns for integrating FastAPI with AutoGen for exposing agents via a REST API.
- **Findings**: FastAPI is well-suited for this task. A dedicated API router can be created for agent interactions. The endpoint (e.g., `/agents/{agent_id}/invoke`) will use the agent manager to retrieve the correct agent instance. The request body will be passed to the agent's `generate_reply()` method. Since agent interactions can be long-running, it's best to run the AutoGen chat in an async task using `asyncio` to avoid blocking the server.

### 3. Hot-Reloading Agent Configurations
- **Task**: Research strategies for hot-reloading agent configurations in a Python application.
- **Findings**: The simplest and most robust approach for a containerized application is to treat the configuration as immutable at runtime. To update an agent, the user should modify the configuration file and then restart the Docker container. This avoids the complexity and potential for memory leaks associated with true hot-reloading. For local development, a file watcher library like `watchdog` can be used to automatically restart the server when config files change.

## Decisions

- **Application Structure**: The application will use a central `AgentManager` class. On startup, the manager will scan the `agent_configs/` directory, parse each YAML file, and create and register an agent for each valid configuration.
- **API Layer**: FastAPI will be used. A single endpoint `POST /agents/{agent_id}/invoke` will handle all agent interactions. The agent execution will be handled asynchronously.
- **Configuration Management**: Agent configurations are loaded at startup. For production, changes will require a container restart. For local development, the server will be configured to restart on file changes.
- **Performance & Scale**: As per the constitution, performance is not a primary goal. The initial design will be simple and synchronous within the agent interaction logic, with async handling at the API layer. This will be sufficient for the target scale of 100 agents and moderate traffic.

## Implementation Kickoff (AutoGen)

To bridge research to working code without disrupting the existing app/tests, we introduce an optional AutoGen adapter and demo:

- Adapter: `src/agents/autogen_adapter.py` – lazy imports AutoGen; provides `run_single_turn(Agent, user_input)`
- Demo: `scripts/run_autogen_demo.py` – standalone script to try AutoGen locally
- Tasks: See `specs/001-ai-agent-hosting-app/tasks.md` → "Optional Add-on: AutoGen Integration"

This approach allows immediate experimentation with AutoGen while keeping the core agent hosting app stable. Later, we can add opt-in endpoints and config mapping when desired.
