# Makefile for AI Agent Hosting Application
# Common development tasks

SHELL := /bin/bash
APP_NAME := ai-agent-app
PORT ?= 8000
OLLAMA_PORT ?= 11434
OLLAMA ?= ollama
OLLAMA_MODELS ?= qwen3:8b
QWEN_VARIANT ?= qwen3:8b
OLLAMA_HOST ?= http://localhost:$(OLLAMA_PORT)

# Python/virtualenv settings
PYTHON ?= python3
VENV_DIR ?= .venv
UV ?= uv
PY_VERSION := $(shell cat .python-version 2>/dev/null)

.PHONY: help python-install install install-venv venv run run-env run-venv test test-venv test-verbose cov cov-html docker-build docker-run docker-run-linux docker-run-linux-hostnet docker-stop docker-clean format format-venv lint lint-venv ollama-pull ollama-pull-qwen ollama-check data-clean keys-generate

help:
	@echo "Available targets:"
	@echo "  help            - Show this help message"
	@echo "  python-install  - Install the Python version from .python-version using uv"
	@echo "  install         - Create venv and install dependencies using uv (respects .python-version if present)"
	@echo "  install-venv    - Create .venv (if missing) and install dependencies inside it using uv (respects .python-version)"
	@echo "  venv            - Create a virtual environment at $(VENV_DIR) using uv (respects .python-version)"
	@echo "  run             - Run the FastAPI app (uvicorn)"
	@echo "  run-env         - Run app with environment file (.env)"
	@echo "  run-venv        - Run the app using $(VENV_DIR)/bin/uvicorn (no activation needed)"
	@echo "  test            - Run tests (pytest)"
	@echo "  test-venv       - Run tests using $(VENV_DIR)/bin/pytest"
	@echo "  test-verbose    - Run tests with verbose output"
	@echo "  cov             - Run tests with coverage report in terminal"
	@echo "  cov-html        - Generate HTML coverage report in ./htmlcov"
	@echo "  docker-build    - Build the Docker image"
	@echo "  docker-run      - Run the Docker container (exposing app)"
	@echo "  docker-run-linux- Run Docker container with Linux-specific options"
	@echo "  docker-run-linux-hostnet - Run Docker container with Linux host networking"
	@echo "  docker-stop     - Stop and remove the Docker container"
	@echo "  docker-clean    - Remove Docker image and container"
	@echo "  format          - Format code using black and isort"
	@echo "  format-venv     - Format code using $(VENV_DIR)/bin/black and $(VENV_DIR)/bin/isort"
	@echo "  lint            - Lint code using flake8 (auto-detect venv if present)"
	@echo "  lint-venv       - Lint code using $(VENV_DIR)/bin/flake8"
	@echo "  ollama-pull     - Pull default OLLAMA models"
	@echo "  ollama-pull-qwen- Pull Qwen model specified by QWEN_VARIANT"
	@echo "  ollama-check    - Check OLLAMA status"
	@echo "  data-clean      - Clean data folder (DATA_DIR, default .data), recreate directory"
	@echo "  keys-generate   - Generate a new API key and append to API_KEYS_FILE (default ./keys.txt)"

python-install:
	@if ! command -v $(UV) >/dev/null 2>&1; then \
		echo "Error: 'uv' not found. Install it via 'brew install uv' or see https://docs.astral.sh/uv/"; \
		exit 1; \
	fi
	@if [ ! -f .python-version ]; then \
		echo "No .python-version file found. Create one with the desired version (e.g., '3.12')."; \
		exit 1; \
	fi
	$(UV) python install "$$(cat .python-version)"

install:
	@if ! command -v $(UV) >/dev/null 2>&1; then \
		echo "Error: 'uv' not found. Install it via 'brew install uv' or see https://docs.astral.sh/uv/"; \
		exit 1; \
	fi
	@if [ ! -d "$(VENV_DIR)" ]; then \
		if [ -f .python-version ]; then \
			$(UV) venv --python "$$(cat .python-version)" $(VENV_DIR); \
		else \
			$(UV) venv $(VENV_DIR); \
		fi; \
	fi
	$(UV) pip sync --python $(VENV_DIR)/bin/python requirements.txt

venv:
	@if ! command -v $(UV) >/dev/null 2>&1; then \
		echo "Error: 'uv' not found. Install it via 'brew install uv' or see https://docs.astral.sh/uv/"; \
		exit 1; \
	fi
	@if [ -f .python-version ]; then \
		$(UV) venv --python "$$(cat .python-version)" $(VENV_DIR); \
	else \
		$(UV) venv $(VENV_DIR); \
	fi
	@echo "Virtualenv created at $(VENV_DIR)"
	@echo "Activate with: source $(VENV_DIR)/bin/activate"

install-venv:
	@if ! command -v $(UV) >/dev/null 2>&1; then \
		echo "Error: 'uv' not found. Install it via 'brew install uv' or see https://docs.astral.sh/uv/"; \
		exit 1; \
	fi
	@if [ ! -d "$(VENV_DIR)" ]; then \
		if [ -f .python-version ]; then \
			$(UV) venv --python "$$(cat .python-version)" $(VENV_DIR); \
		else \
			$(UV) venv $(VENV_DIR); \
		fi; \
		echo "Virtualenv created at $(VENV_DIR)"; \
	fi
	$(UV) pip sync --python $(VENV_DIR)/bin/python requirements.txt

run:
	uvicorn src.main:app --host 0.0.0.0 --port $(PORT)

run-env:
	set -a; [ -f .env ] && . ./.env; set +a; \
	uvicorn src.main:app --host 0.0.0.0 --port $(PORT)

run-venv:
	@if [ ! -d "$(VENV_DIR)" ]; then \
		$(PYTHON) -m venv $(VENV_DIR); \
	fi
	$(VENV_DIR)/bin/uvicorn src.main:app --host 0.0.0.0 --port $(PORT)

# Tests

test:
	pytest -q

test-verbose:
	pytest -rs

# Coverage
cov:
	pytest --cov=src --cov-report=term-missing

cov-html:
	pytest --cov=src --cov-report=html && echo "Coverage report -> htmlcov/index.html"

# Docker
docker-build:
	docker build -f docker/studio.Dockerfile -t $(APP_NAME) .

docker-run:
	- docker rm -f $(APP_NAME)-dev >/dev/null 2>&1 || true
	docker run -d --name $(APP_NAME)-dev -p $(PORT):8000 \
	  -v $(shell pwd)/agent_configs:/app/agent_configs \
	  -e API_KEY=$${API_KEY:-changeme} \
	  -e AGENT_CONFIG_DIR=/app/agent_configs \
	  -e OLLAMA_HOST=$${OLLAMA_HOST:-http://host.docker.internal:$(OLLAMA_PORT)} \
	  $(APP_NAME)

docker-run-linux:
	- docker rm -f $(APP_NAME)-dev >/dev/null 2>&1 || true
	# Requires Docker 20.10+ for --add-host=...:host-gateway
	docker run -d --name $(APP_NAME)-dev -p $(PORT):8000 \
	  -v $(shell pwd)/agent_configs:/app/agent_configs \
	  --add-host=host.docker.internal:host-gateway \
	  -e API_KEY=$${API_KEY:-changeme} \
	  -e AGENT_CONFIG_DIR=/app/agent_configs \
	  -e OLLAMA_HOST=$${OLLAMA_HOST:-http://host.docker.internal:$(OLLAMA_PORT)} \
	  $(APP_NAME)

docker-run-linux-hostnet:
	- docker rm -f $(APP_NAME)-dev >/dev/null 2>&1 || true
	docker run -d --name $(APP_NAME)-dev --network host \
	  -v $(shell pwd)/agent_configs:/app/agent_configs \
	  -e API_KEY=$${API_KEY:-changeme} \
	  -e AGENT_CONFIG_DIR=/app/agent_configs \
	  -e OLLAMA_HOST=$${OLLAMA_HOST:-http://localhost:$(OLLAMA_PORT)} \
	  $(APP_NAME)

docker-stop:
	- docker rm -f $(APP_NAME)-dev || true

docker-clean:
	- docker rmi $(APP_NAME) || true

# Ollama model management
ollama-pull:
	@for model in $(OLLAMA_MODELS); do \
		echo "Pulling $$model via Ollama..."; \
		$(OLLAMA) pull $$model || exit $$?; \
	done

ollama-pull-qwen:
	@echo "Pulling Qwen variant: $(QWEN_VARIANT) via Ollama..."
	$(OLLAMA) pull $(QWEN_VARIANT)

ollama-check:
	@echo "Checking Ollama at $(OLLAMA_HOST)/api/tags"
	@if command -v jq >/dev/null 2>&1; then \
		curl -s -f "$(OLLAMA_HOST)/api/tags" | jq; \
	else \
		curl -s -f "$(OLLAMA_HOST)/api/tags"; \
	fi

# Formatting & linting
LINT_PATHS ?= src tests
FORMAT_PATHS ?= src tests
format:
	@if [ -x "$(VENV_DIR)/bin/black" ] && [ -x "$(VENV_DIR)/bin/isort" ]; then \
		"$(VENV_DIR)/bin/black" $(FORMAT_PATHS) && "$(VENV_DIR)/bin/isort" $(FORMAT_PATHS); \
	elif command -v black >/dev/null 2>&1 && command -v isort >/dev/null 2>&1; then \
		black $(FORMAT_PATHS) && isort $(FORMAT_PATHS); \
	else \
		echo "black/isort not found. Run 'make format-venv' to install in .venv"; \
		exit 127; \
	fi

format-venv:
	@if [ ! -d "$(VENV_DIR)" ]; then \
		if command -v $(UV) >/dev/null 2>&1; then \
			$(UV) venv $(VENV_DIR); \
		else \
			$(PYTHON) -m venv $(VENV_DIR); \
		fi; \
	fi
	@if command -v $(UV) >/dev/null 2>&1; then \
		$(UV) pip install --python $(VENV_DIR)/bin/python -q -U black isort; \
	else \
		"$(VENV_DIR)/bin/python" -m pip install --upgrade pip; \
		"$(VENV_DIR)/bin/python" -m pip install -U black isort; \
	fi
	"$(VENV_DIR)/bin/black" $(FORMAT_PATHS) && "$(VENV_DIR)/bin/isort" $(FORMAT_PATHS)

lint:
	@if [ -x "$(VENV_DIR)/bin/flake8" ]; then \
		"$(VENV_DIR)/bin/flake8" --max-line-length 100 --ignore E203,W503 $(LINT_PATHS); \
	elif command -v flake8 >/dev/null 2>&1; then \
		flake8 --max-line-length 100 --ignore E203,W503 $(LINT_PATHS); \
	else \
		echo "flake8 not found. Install deps with 'make install' or run 'make lint-venv' after creating the venv."; \
		exit 1; \
	fi

lint-venv:
	@if [ ! -d "$(VENV_DIR)" ]; then \
		$(UV) venv $(VENV_DIR); \
	fi
	@if [ ! -x "$(VENV_DIR)/bin/flake8" ]; then \
		$(UV) pip install --python $(VENV_DIR)/bin/python flake8; \
	fi
	"$(VENV_DIR)/bin/flake8" --max-line-length 100 --ignore E203,W503 $(LINT_PATHS)

# Data cleanup
# Removes files inside DATA_DIR (or .data by default) and recreates the directory
# Includes hidden files; safe if directory is empty or missing
# Usage: make data-clean [DATA_DIR=.data]
data-clean:
	@DIR="$${DATA_DIR:-.data}"; \
	echo "Cleaning data dir $$DIR"; \
	mkdir -p "$$DIR"; \
	rm -rf "$$DIR"/* "$$DIR"/.[!.]* "$$DIR"/..?*

# Generate and append a new API key to file
# Uses API_KEYS_FILE or defaults to ./keys.txt
# Creates file and parent directory if needed; set file mode to 600
# Prints the new key for your convenience
keys-generate:
	@KEY_FILE="$${API_KEYS_FILE:-$(shell pwd)/keys.txt}"; \
	mkdir -p "$$(dirname "$$KEY_FILE")"; \
	touch "$$KEY_FILE"; \
	chmod 600 "$$KEY_FILE"; \
	if command -v openssl >/dev/null 2>&1; then \
	  NEW_KEY=$$(openssl rand -base64 32 | tr -d '\n'); \
	else \
	  NEW_KEY=$$(python3 - <<'PY'\
import secrets\
print(secrets.token_urlsafe(32))\
PY\
); \
	fi; \
	echo "$$NEW_KEY" >> "$$KEY_FILE"; \
	echo "Added new API key to $$KEY_FILE:"; \
	echo "$$NEW_KEY"
# Run tests using virtualenv without activating it

test-venv:
	@if [ ! -d "$(VENV_DIR)" ]; then \
		$(PYTHON) -m venv $(VENV_DIR); \
	fi
	$(VENV_DIR)/bin/pytest -q