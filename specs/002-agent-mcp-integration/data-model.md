# Data Model: Agent MCP Integration and Knowledge Store

This document defines the data models for the key entities in this feature.

## KnowledgeEntry

Represents a single entry in the knowledge store.

| Field | Type | Description | Constraints |
|---|---|---|---|
| `id` | Integer | Unique identifier for the entry. | Primary Key, Auto-incrementing |
| `title` | String | The title of the knowledge entry. | Required |
| `content` | Text | The main text content of the entry. | Required |
| `vector` | Blob | The vector embedding of the content. | Required |
| `author` | String | The author of the knowledge entry. | Optional |
| `creation_date` | DateTime | The date and time when the entry was created. | Required, Default: current time |
| `tags` | String | Comma-separated list of tags for the entry. | Optional |

## MCP Server Configuration

Represents the configuration for an MCP server, stored in a JSON file.

| Field | Type | Description |
|---|---|---|
| `name` | String | A unique name for the MCP server. |
| `url` | String | The URL of the MCP server. |
| `description` | String | A description of the server and its capabilities. |
| `tools` | Array of Objects | A list of tools available on the server. |

Each object in the `tools` array will have the following structure:

| Field | Type | Description |
|---|---|---|
| `name` | String | The name of the tool. |
| `description` | String | A description of what the tool does. |

## Agent Configuration

The existing agent configuration (in YAML) will be extended to include a reference to the MCP server configurations.

```yaml
agent:
  name: my_agent
  # ... other agent settings
  mcp_servers:
    - mcp_server_1
    - mcp_server_2
```
