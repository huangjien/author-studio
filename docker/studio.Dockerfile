# Dockerfile for AI Agent Hosting Application
FROM python:3.13-slim

# Prevent Python from writing .pyc files and enable output buffering
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (optional) and Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application source
COPY src /app/src
COPY agent_configs /app/agent_configs

# Create data directory for file-based persistence
RUN mkdir -p /app/.data

# Default environment configuration (can be overridden at runtime)
ENV AGENT_CONFIG_DIR="/app/agent_configs" \
    PERSISTENCE_MODE="file" \
    DATA_DIR="/app/.data" \
    API_KEYS_FILE="/app/.data/api_keys.txt"

# Copy and use entrypoint for secure API key generation on first startup
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

# Start via entrypoint (generates/persists API_KEY if unset and logs it)
ENTRYPOINT ["/app/entrypoint.sh"]
