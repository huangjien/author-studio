# Dockerfile for AI Agent Hosting Application
FROM python:3.11-slim

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
ENV API_KEY="changeme" \
    AGENT_CONFIG_DIR="/app/agent_configs" \
    PERSISTENCE_MODE="file" \
    DATA_DIR="/app/.data"

EXPOSE 8000

# Start the FastAPI app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]