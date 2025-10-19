# Research: Agent MCP Integration and Knowledge Store

This document outlines the research and decisions made for the technical implementation of the feature.

## MCP Server Configuration

-   **Decision**: MCP servers will be defined in a separate JSON file. Agent configurations in YAML will reference these server definitions.
-   **Rationale**: This approach decouples the agent configuration from the MCP server details, making it easier to manage and reuse server configurations across multiple agents. JSON is a widely supported and human-readable format for this purpose.
-   **Alternatives considered**: Defining MCP servers directly in the agent YAML files was considered but rejected to avoid duplication and improve maintainability.

## Embedding LLM

-   **Decision**: The default embedding LLM will be `Qwen3-Embedding:latest` from Ollama.
-   **Rationale**: The user explicitly requested this model. Ollama provides a convenient way to run and manage local LLMs.
-   **Alternatives considered**: Other embedding models could be used, but the user's preference is clear.

## Vector Storage

-   **Decision**: SQLite will be used for both structured data and as a vector store.
-   **Rationale**: SQLite is a lightweight, file-based database that is easy to set up and use, especially in a Dockerized environment. For vector storage, extensions like `sqlite-vss` can be used to provide vector search capabilities directly within SQLite, avoiding the need for a separate vector database for this scale.
-   **Alternatives considered**: A dedicated vector database like Chroma or Weaviate was considered, but for the specified scale of 1 million entries, a SQLite-based solution is sufficient and simpler to manage.

## Agent MCP Server Selection

-   **Decision**: The agent will decide which MCP server to call based on the descriptions of the tools available on each MCP server.
-   **Rationale**: This is a flexible and powerful approach that allows the agent to dynamically select the most appropriate tool for a given task. It requires the MCP servers to provide clear and descriptive information about their available tools.
-   **Alternatives considered**: A simpler approach of using a predefined order or a fixed server per agent was rejected in favor of this more intelligent selection mechanism.
