# Quickstart: Agent MCP Integration and Knowledge Store

This guide provides instructions on how to set up and run the new services introduced in this feature.

## Prerequisites

-   Docker and Docker Compose
-   Ollama with the `Qwen3-Embedding:latest` model pulled.

## Setup

1.  **Create MCP Server Configuration:**
    Create a file named `mcp_servers.json` in the root of the project with the following structure:

    ```json
    [
      {
        "name": "mcp_server_1",
        "url": "http://mcp-server-1.example.com",
        "description": "A server for general knowledge.",
        "tools": [
          {
            "name": "search",
            "description": "Searches for information on a given topic."
          }
        ]
      }
    ]
    ```

2.  **Update Agent Configuration:**
    In your agent's YAML configuration file, add a reference to the MCP servers:

    ```yaml
    agent:
      name: my_agent
      # ... other agent settings
      mcp_servers:
        - mcp_server_1
    ```

3.  **Create Docker Compose Override:**
    Create a `docker-compose.override.yml` file to mount the `mcp_servers.json` file into the application container:

    ```yaml
    version: '3.8'
    services:
      app:
        volumes:
          - ./mcp_servers.json:/app/mcp_servers.json
    ```

## Running the Application

1.  **Start the services:**
    ```bash
    docker-compose up -d
    ```

2.  **Check the status of the MCP servers:**
    ```bash
    curl http://localhost:8000/mcp/status
    ```

3.  **Add a knowledge entry:**
    ```bash
    curl -X POST http://localhost:8000/knowledge -H "Content-Type: application/json" -d '{
      "title": "My first entry",
      "content": "This is the content of my first entry.",
      "author": "John Doe",
      "tags": "test, example"
    }'
    ```

4.  **Search for a knowledge entry:**
    ```bash
    curl -X POST http://localhost:8000/knowledge/search -H "Content-Type: application/json" -d '{
      "query": "first entry"
    }'
    ```
