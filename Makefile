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
PY_FALLBACK := 3.13
FORMAT_PATHS ?= src tests
LINT_PATHS ?= src tests

.PHONY: help setup run test docker-build docker-run docker-stop docker-clean format lint lint-no-tests ollama-check data-clean keys-generate autogen-install setup-autogen run-autogen test-autogen

help:
	@echo "Available targets:"
	@echo "  help            - Show this help message"
	@echo "  setup           - Detect and install Python (via uv), create .venv, and install dependencies"
	@echo "  setup-autogen   - Setup venv/deps and install autogen-stable extras (AgentChat + MCP)"
	@echo "  autogen-install - Install autogen-stable extras into the venv"
	@echo "  run             - Run the FastAPI app (auto-creates .venv, loads .env)"
	@echo "  run-autogen     - Run the app with AGENTS_USE_AUTOGEN=1 after installing autogen-stable"
	@echo "  test            - Run tests (auto-creates .venv, loads .env)"
	@echo "  test-autogen    - Run tests with AGENTS_USE_AUTOGEN=1 after installing autogen-stable"
	@echo "  docker-build    - Build the Docker image"
	@echo "  docker-run      - Run the Docker container (auto-detect OS; uses host network on Linux)"
	@echo "  docker-stop     - Stop and remove the Docker container"
	@echo "  docker-clean    - Remove Docker image and container"
	@echo "  format          - Format code (black + isort) via $(VENV_DIR) and .env"
	@echo "  lint            - Lint code (flake8) via $(VENV_DIR) and .env"
	@echo "  lint-no-tests   - Lint only app code (exclude tests) via $(VENV_DIR) and .env"
	@echo "  ollama-check    - Check OLLAMA status"
	@echo "  data-clean      - Clean data folder (DATA_DIR, default .data), recreate directory"
	@echo "  keys-generate   - Generate a new API key and append to API_KEYS_FILE (default ./keys.txt)"

python-install install install-venv install-env venv:
	@$(MAKE) setup

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

# Simplified workflow: ensure venv + .env for run/test/format/lint
.PHONY: ensure-venv ensure-deps setup run test format lint docker-run
LOAD_ENV = set -a; [ -f .env ] && . ./.env; set +a

ensure-venv:
	@if [ -d "$(VENV_DIR)" ]; then \
		CUR_VER=$$("$(VENV_DIR)/bin/python" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")'); \
		CUR_MINOR=$$(echo $$CUR_VER | cut -d. -f2); \
		if [ "$$CUR_MINOR" -ge 14 ]; then \
			echo "Existing venv uses Python $$CUR_VER which is unsupported by some deps; rebuilding with $(PY_FALLBACK)"; \
			rm -rf "$(VENV_DIR)"; \
		fi; \
	fi
	@if command -v $(UV) >/dev/null 2>&1 && [ -f .python-version ]; then \
		REQ_PY=$$(cat .python-version); \
		MAJOR=$${REQ_PY%%.*}; MINOR=$$(echo $$REQ_PY | cut -d. -f2); \
		if [ "$$MAJOR" = "3" ] && [ "$$MINOR" -ge 14 ]; then \
			echo "Requested Python $$REQ_PY but some dependencies lack 3.14 support; falling back to $(PY_FALLBACK)"; \
			REQ_PY=$(PY_FALLBACK); \
		fi; \
		$(UV) python install "$$REQ_PY"; \
	fi
	@if [ ! -d "$(VENV_DIR)" ]; then \
		if command -v $(UV) >/dev/null 2>&1; then \
			if [ -f .python-version ]; then \
				REQ_PY=$$(cat .python-version); \
				MAJOR=$${REQ_PY%%.*}; MINOR=$$(echo $$REQ_PY | cut -d. -f2); \
				if [ "$$MAJOR" = "3" ] && [ "$$MINOR" -ge 14 ]; then \
					echo "Using Python $(PY_FALLBACK) to create venv for compatibility"; \
					REQ_PY=$(PY_FALLBACK); \
				fi; \
				$(UV) venv --python "$$REQ_PY" $(VENV_DIR); \
			else \
				$(UV) venv $(VENV_DIR); \
			fi; \
		else \
			$(PYTHON) -m venv $(VENV_DIR); \
		fi; \
	fi

ensure-deps: ensure-venv
	@if command -v $(UV) >/dev/null 2>&1; then \
		$(UV) pip install --python $(VENV_DIR)/bin/python -r requirements.txt; \
	else \
		"$(VENV_DIR)/bin/python" -m pip install -r requirements.txt; \
	fi

setup: ensure-deps

run: ensure-deps
	@$(LOAD_ENV); \
	"$(VENV_DIR)/bin/uvicorn" src.main:app --host 0.0.0.0 --port $(PORT)

test: ensure-deps
	@$(LOAD_ENV); \
	"$(VENV_DIR)/bin/pytest" -q

format: ensure-deps
	@$(LOAD_ENV); \
	"$(VENV_DIR)/bin/isort" $(FORMAT_PATHS) && "$(VENV_DIR)/bin/black" $(FORMAT_PATHS)
	@if [ -x "$(VENV_DIR)/bin/pre-commit" ]; then \
		$(LOAD_ENV); "$(VENV_DIR)/bin/pre-commit" run end-of-file-fixer -a || true; \
		$(LOAD_ENV); "$(VENV_DIR)/bin/pre-commit" run trailing-whitespace -a || true; \
	fi

lint: ensure-deps
	@$(LOAD_ENV); \
	"$(VENV_DIR)/bin/flake8" --max-line-length 100 --ignore E203,W503 $(LINT_PATHS)

lint-no-tests: ensure-deps
	@$(LOAD_ENV); \
	"$(VENV_DIR)/bin/flake8" --max-line-length 100 --ignore E203,W503 src

ollama-check:
	@$(LOAD_ENV); \
	OLLAMA_DEF=$${OLLAMA_HOST:-http://localhost:$(OLLAMA_PORT)}; \
	if ! echo "$$OLLAMA_DEF" | grep -Eq '^https?://'; then \
		OLLAMA_DEF="http://$$OLLAMA_DEF"; \
	fi; \
	URL="$${OLLAMA_DEF%/}/api/tags"; \
	echo "Checking Ollama at $$URL"; \
	STATUS=$$(curl -s -m 3 -o /dev/null -w '%{http_code}' "$$URL" || true); \
	if [ "$$STATUS" = "200" ]; then \
		echo "Ollama OK (HTTP $$STATUS)"; \
		if command -v jq >/dev/null 2>&1; then \
			curl -s "$$URL" | jq '{models_count: (.models | length)}'; \
		fi; \
	else \
		echo "Ollama NOT reachable (HTTP $$STATUS)"; \
		echo "Resolved host: $$OLLAMA_DEF"; \
		echo "Tips:"; \
		echo " - Ensure Ollama is installed and running: https://ollama.com/"; \
		echo " - Default host is http://localhost:$(OLLAMA_PORT); override with OLLAMA_HOST env var"; \
		echo " - On macOS/Windows with Docker, use OLLAMA_HOST=http://host.docker.internal:$(OLLAMA_PORT)"; \
		exit 1; \
	fi

# Auto docker run: detect OS and choose networking
# - Linux: use host network for access to localhost services (e.g., Ollama)
# - macOS/Windows: use port mapping, and host.docker.internal for Ollama

docker-build:
	docker build -f docker/studio.Dockerfile -t $(APP_NAME) .

docker-run:
	@OS=`uname -s`; \
	if [ "$$OS" = "Linux" ]; then \
		echo "Running Docker (Linux, host network)"; \
		docker rm -f $(APP_NAME)-dev >/dev/null 2>&1 || true; \
		OLLAMA_DEF=$${OLLAMA_HOST:-http://localhost:$(OLLAMA_PORT)}; \
		docker run -d --name $(APP_NAME)-dev --network host \
		  -v "$(shell pwd)/agent_configs:/app/agent_configs" \
		  --env-file .env \
		  -e AGENT_CONFIG_DIR=/app/agent_configs \
		  -e OLLAMA_HOST="$$OLLAMA_DEF" \
		  $(APP_NAME); \
	else \
		echo "Running Docker (macOS/Windows, port mapping)"; \
		docker rm -f $(APP_NAME)-dev >/dev/null 2>&1 || true; \
		OLLAMA_DEF=$${OLLAMA_HOST:-http://host.docker.internal:$(OLLAMA_PORT)}; \
		docker run -d --name $(APP_NAME)-dev -p $(PORT):8000 \
		  -v "$(shell pwd)/agent_configs:/app/agent_configs" \
		  --env-file .env \
		  -e AGENT_CONFIG_DIR=/app/agent_configs \
		  -e OLLAMA_HOST="$$OLLAMA_DEF" \
		  $(APP_NAME); \
	fi

# Install AutoGen AgentChat and MCP extensions via project extra
# Uses uv if available; otherwise falls back to pip in the venv
autogen-install: ensure-venv
	@if command -v $(UV) >/dev/null 2>&1; then \
		$(UV) pip install --python $(VENV_DIR)/bin/python autogen-agentchat==0.7.5 "autogen-ext[openai,mcp]==0.7.5"; \
	else \
		"$(VENV_DIR)/bin/python" -m pip install autogen-agentchat==0.7.5 "autogen-ext[openai,mcp]==0.7.5"; \
	fi

# Setup including AutoGen extras
setup-autogen: ensure-deps autogen-install

# Run the app with AutoGen enabled, ensuring extras are installed
run-autogen: ensure-deps autogen-install
	@$(LOAD_ENV); \
	AGENTS_USE_AUTOGEN=1 "$(VENV_DIR)/bin/uvicorn" src.main:app --host 0.0.0.0 --port $(PORT)

# Run tests with AutoGen enabled
test-autogen: ensure-deps autogen-install
	@$(LOAD_ENV); \
	AGENTS_USE_AUTOGEN=1 "$(VENV_DIR)/bin/pytest" -q
