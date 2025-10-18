# Quickstart: AI Agent Hosting Application

This guide provides a brief overview of how to get the application running and interact with an agent.

## 1. Create an Agent Configuration

Create a file named `my_assistant.yaml` in the `agent_configs/` directory with the following content:

```yaml
name: my_assistant
llm:
  provider: ollama
  config:
    model: qwen3:8b
    base_url: http://host.docker.internal:11434/v1
prompts:
  en: "You are a helpful assistant."
tools: []
workflow:
  type: simple
```

## 2. Build and Run with Docker

From the root of the project, build and run the Docker container:

```bash
# Build the Docker image
docker build -t ai-agent-app .

# Run the container, mounting the agent configurations directory
docker run -p 8000:8000 -v ./agent_configs:/app/agent_configs -e API_KEY="your-secret-api-key" ai-agent-app
```
*Note: The Ollama `base_url` uses `host.docker.internal` to allow the container to access a service running on the host machine.*

## 3. Interact with the Agent

Once the container is running, you can interact with your agent using `curl` or any API client.

```bash
curl -X POST http://localhost:8000/agents/my_assistant/invoke \
-H "Content-Type: application/json" \
-H "X-API-Key: your-secret-api-key" \
-d 
'{'
  "input": "Hello, who are you?"
'}'
```

You should receive a JSON response from the agent:

```json
{
  "agent_id": "my_assistant",
  "session_id": "some-unique-session-id",
  "output": "[my_assistant] Echo: Hello, who are you?"
}
```

## 4. Internationalization (i18n)

You can request localized responses using the `Accept-Language` header. The application will select the best matching prompt from the agent configuration, falling back to English (`en`) if unavailable.

Supported languages depend on the prompts defined in your agent config. Example keys: `zh-CN`, `zh-TW`, `en`, `es`, `de`, `fr`, `it`, `ru`, `ko`, `jp`.

Example:
```bash
curl -X POST http://localhost:8000/agents/example-agent/invoke \
 -H "Content-Type: application/json" \
 -H "X-API-Key: your-secret-api-key" \
 -H "Accept-Language: es-ES,es;q=0.9" \
 -d '{"input": "Hola"}'
```
The response includes the selected language key:
```json
{
  "agent_id": "example-agent",
  "session_id": "...",
  "output": "[example-agent] Eres un asistente útil. :: Echo: Hola",
  "selected_language": "es"
}
```
