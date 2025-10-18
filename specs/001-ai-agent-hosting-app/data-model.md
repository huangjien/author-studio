# Data Model: AI Agent Hosting Application

This document defines the key data entities for the application, based on the feature specification. These are conceptual models; the implementation will translate them into appropriate Python classes.

### Agent
Represents a configured and loaded AI agent, ready to be invoked.

| Attribute | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `agent_id` | String | A unique identifier for the agent, derived from its config filename. | `example_agent` |
| `llm_config` | Object | Configuration for the LLM, including model name and API keys. | `{ "model": "qwen3:8b", "base_url": "http://localhost:11434/v1" }` |
| `workflow` | Object | Defines the agent's operational logic. | `{ "type": "group_chat", "human_in_loop": "optional" }` |
| `prompts` | Object | A dictionary of prompts, keyed by language code. | `{ "en": "You are a helpful assistant.", "es": "Eres un asistente útil." }` |
| `tools` | Array | A list of tools (functions) the agent can use. | `["web_search", "calculator"]` |

### Agent Configuration
A file-based representation of an agent's properties, defined in YAML.

| Field | Type | Description |
| :--- | :--- | :--- |
| `name` | String | The unique name/ID for the agent. |
| `llm` | Object | LLM connection details (model, provider, credentials). |
| `workflow` | Object | Workflow type and settings (e.g., human-in-loop). |
| `prompts` | Object | Language-specific system prompts and user prompts. |
| `tools` | Array | List of enabled tool names. |

### Session / Conversation
Represents a single, stateful interaction with an agent.

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `session_id` | String | A unique identifier for the conversation. |
| `agent_id` | String | The ID of the agent involved in the session. |
| `history` | Array | A log of messages exchanged between the user and the agent. |
| `status` | String | The current status of the session (e.g., `active`, `paused_for_human`, `completed`). |
| `created_at` | DateTime | Timestamp of when the session was created. |
