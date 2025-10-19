import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.agents.registry import AgentRegistry
from src.api.routes.agents import router as agents_router
from src.api.routes.autogen import router as autogen_router
from src.api.routes.knowledge import router as knowledge_router
from src.api.routes.mcp import router as mcp_router
from src.config.env import settings
from src.core.database import init_db
from src.services.mcp_manager import mcp_client_manager

from .services.logging import init_logging

# Request context for logging middleware
REQUEST_CONTEXT: ContextVar[Dict[str, Any]] = ContextVar("REQUEST_CONTEXT", default={})


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        ctx = REQUEST_CONTEXT.get({})
        record.request_id = ctx.get("request_id")
        record.path = ctx.get("path")
        record.method = ctx.get("method")
        record.client_ip = ctx.get("client_ip")
        return True


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    # Initialize logging
    init_logging()
    # Attach request context filter to all handlers
    root_logger = logging.getLogger()
    req_filter = RequestContextFilter()
    for h in root_logger.handlers:
        try:
            h.addFilter(req_filter)
        except Exception:
            pass
    # Ensure local SQLite DB file exists
    await init_db()
    # Load MCP servers config for status endpoint
    mcp_client_manager.load_servers_config(os.getenv("MCP_SERVERS_PATH", "mcp_servers.json"))
    # Initialize Knowledge tables (ignore if aiosqlite is unavailable)
    try:
        from src.services.knowledge_service import KnowledgeService

        await KnowledgeService().init_tables()
    except Exception:
        # optional dependency; skip on error
        pass
    # Populate health info cache
    global HEALTH_INFO
    HEALTH_INFO = _build_health_info()
    yield


app = FastAPI(title="AI Agent Hosting Application", version="0.1.0", lifespan=app_lifespan)


# HTTP middleware to inject request metadata into logging records
@app.middleware("http")
async def inject_request_metadata(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    ctx = {
        "request_id": rid,
        "path": request.url.path,
        "method": request.method,
        "client_ip": request.client.host if request.client else None,
    }
    token = REQUEST_CONTEXT.set(ctx)
    try:
        response = await call_next(request)
    finally:
        REQUEST_CONTEXT.reset(token)
    # Echo back request id header for tracing
    response.headers["x-request-id"] = rid
    return response


# Global cache populated at startup
HEALTH_INFO: Dict[str, Any] = {}


def _detect_llm_providers(env: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """Return a map of provider -> {configured, available, details} based on env vars.
    We do not perform network calls here; this is purely configuration-driven.
    """
    providers: Dict[str, Dict[str, Any]] = {}

    def present(key: str) -> bool:
        v = env.get(key)
        return bool(v and v.strip())

    # Cloud providers
    providers["openai"] = {
        "configured": present("OPENAI_API_KEY"),
        "available": present("OPENAI_API_KEY"),
        "details": {"env": "OPENAI_API_KEY"},
    }
    providers["anthropic"] = {
        "configured": present("ANTHROPIC_API_KEY"),
        "available": present("ANTHROPIC_API_KEY"),
        "details": {"env": "ANTHROPIC_API_KEY"},
    }
    providers["gemini"] = {
        "configured": present("GEMINI_API_KEY"),
        "available": present("GEMINI_API_KEY"),
        "details": {"env": "GEMINI_API_KEY"},
    }
    providers["azure_openai"] = {
        "configured": (present("AZURE_OPENAI_API_KEY") and present("AZURE_OPENAI_ENDPOINT")),
        "available": (present("AZURE_OPENAI_API_KEY") and present("AZURE_OPENAI_ENDPOINT")),
        "details": {"env": ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"]},
    }
    providers["mistral"] = {
        "configured": present("MISTRAL_API_KEY"),
        "available": present("MISTRAL_API_KEY"),
        "details": {"env": "MISTRAL_API_KEY"},
    }
    providers["cohere"] = {
        "configured": present("COHERE_API_KEY"),
        "available": present("COHERE_API_KEY"),
        "details": {"env": "COHERE_API_KEY"},
    }
    providers["together"] = {
        "configured": present("TOGETHER_API_KEY"),
        "available": present("TOGETHER_API_KEY"),
        "details": {"env": "TOGETHER_API_KEY"},
    }

    # DeepSeek provider (OpenAI-compatible API)
    providers["deepseek"] = {
        "configured": present("DEEPSEEK_API_KEY"),
        "available": present("DEEPSEEK_API_KEY"),
        "details": {
            "env": "DEEPSEEK_API_KEY",
            "base_url": "https://api.deepseek.com",
            "chat_completions": "https://api.deepseek.com/chat/completions",
        },
    }

    # Local provider (Ollama). We consider it "configured" if OLLAMA_HOST is set.
    # We do not attempt to ping it here; the Makefile provides a connectivity check.
    default_host = f"http://localhost:{env.get('OLLAMA_PORT', '11434')}"
    ollama_host = env.get("OLLAMA_HOST", default_host)
    providers["ollama"] = {
        "configured": present("OLLAMA_HOST"),
        "available": present("OLLAMA_HOST"),
        "details": {
            "env": "OLLAMA_HOST",
            "default_host": default_host,
            "resolved_host": ollama_host,
        },
    }

    return providers


def _build_health_info() -> Dict[str, Any]:
    env = dict(os.environ)
    providers = _detect_llm_providers(env)

    # Load agents from configured directory
    registry = AgentRegistry()
    registry.reload(settings.agent_config_dir)

    agents_info = []
    for agent in registry.list_agents():
        provider = (agent.llm_config or {}).get("provider", "").lower().strip()
        model = (agent.llm_config or {}).get("model", "")
        languages = sorted(list((agent.prompts or {}).keys()))
        available = providers.get(provider, {}).get("available", False)
        agents_info.append(
            {
                "agent_id": agent.agent_id,
                "provider": provider,
                "model": model,
                "languages": languages,
                "available": bool(available),
            }
        )

    return {
        "status": "ok",
        "llm_providers": providers,
        "agents": agents_info,
        "agent_count": registry.count(),
    }


def _probe_http(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout_ms: int = 2000,
) -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout_ms / 1000.0) as client:
            resp = client.get(url, headers=headers or {})
            elapsed = (time.perf_counter() - start) * 1000.0
            return {
                "ok": resp.status_code < 500,
                "status_code": resp.status_code,
                "latency_ms": round(elapsed, 2),
                "error": None,
            }
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000.0
        return {
            "ok": False,
            "status_code": None,
            "latency_ms": round(elapsed, 2),
            "error": str(e),
        }


def _live_connectivity(
    env: Dict[str, str],
    providers: Dict[str, Dict[str, Any]],
    targets: Optional[List[str]] = None,
    timeout_ms: int = 2000,
) -> Dict[str, Any]:
    results: Dict[str, Any] = {}

    def want(name: str) -> bool:
        return not targets or name in targets

    # Ollama: try resolved host regardless of configured flag for convenience
    if want("ollama"):
        default_host = f"http://localhost:{env.get('OLLAMA_PORT', '11434')}"
        ollama_host = env.get("OLLAMA_HOST", default_host)
        tags_url = ollama_host.rstrip("/") + "/api/tags"
        results["ollama"] = _probe_http(tags_url, timeout_ms=timeout_ms) | {
            "endpoint": tags_url,
            "configured": providers["ollama"]["configured"],
        }

    # OpenAI
    if want("openai") and providers.get("openai", {}).get("configured"):
        url = "https://api.openai.com/v1/models"
        headers = {"Authorization": f"Bearer {env.get('OPENAI_API_KEY', '')}"}
        results["openai"] = _probe_http(url, headers=headers, timeout_ms=timeout_ms) | {
            "endpoint": url
        }

    # Anthropic
    if want("anthropic") and providers.get("anthropic", {}).get("configured"):
        url = "https://api.anthropic.com/v1/models"
        headers = {
            "x-api-key": env.get("ANTHROPIC_API_KEY", ""),
            "anthropic-version": "2023-06-01",
        }
        results["anthropic"] = _probe_http(url, headers=headers, timeout_ms=timeout_ms) | {
            "endpoint": url
        }

    # Gemini (Google Generative Language)
    if want("gemini") and providers.get("gemini", {}).get("configured"):
        key = env.get("GEMINI_API_KEY", "")
        url = f"https://generativelanguage.googleapis.com/v1/models?key={key}"
        results["gemini"] = _probe_http(url, timeout_ms=timeout_ms) | {"endpoint": url}

    # Azure OpenAI
    if want("azure_openai") and providers.get("azure_openai", {}).get("configured"):
        endpoint = env.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        url = f"{endpoint}/openai/models?api-version=2024-05-01-preview"
        headers = {"api-key": env.get("AZURE_OPENAI_API_KEY", "")}
        results["azure_openai"] = _probe_http(url, headers=headers, timeout_ms=timeout_ms) | {
            "endpoint": url
        }

    # Mistral
    if want("mistral") and providers.get("mistral", {}).get("configured"):
        url = "https://api.mistral.ai/v1/models"
        headers = {"Authorization": f"Bearer {env.get('MISTRAL_API_KEY', '')}"}
        results["mistral"] = _probe_http(url, headers=headers, timeout_ms=timeout_ms) | {
            "endpoint": url
        }

    # Cohere
    if want("cohere") and providers.get("cohere", {}).get("configured"):
        url = "https://api.cohere.ai/v1/models"
        headers = {"Authorization": f"Bearer {env.get('COHERE_API_KEY', '')}"}
        results["cohere"] = _probe_http(url, headers=headers, timeout_ms=timeout_ms) | {
            "endpoint": url
        }

    # Together
    if want("together") and providers.get("together", {}).get("configured"):
        url = "https://api.together.xyz/v1/models"
        headers = {"Authorization": f"Bearer {env.get('TOGETHER_API_KEY', '')}"}
        results["together"] = _probe_http(url, headers=headers, timeout_ms=timeout_ms) | {
            "endpoint": url
        }

    # DeepSeek (OpenAI-compatible)
    if want("deepseek") and providers.get("deepseek", {}).get("configured"):
        url = "https://api.deepseek.com/v1/models"
        headers = {"Authorization": f"Bearer {env.get('DEEPSEEK_API_KEY', '')}"}
        results["deepseek"] = _probe_http(url, headers=headers, timeout_ms=timeout_ms) | {
            "endpoint": url
        }

    summary_ok = all(v.get("ok") for v in results.values()) if results else False
    return {"results": results, "live_ok": summary_ok}


# Include routers at import time to ensure routes are available to TestClient and during app startup
app.include_router(agents_router)
app.include_router(mcp_router)
app.include_router(knowledge_router)
# Feature-flagged AutoGen router
if settings.autogen_enabled:
    app.include_router(autogen_router)


@app.get("/health")
def health_check(
    live: bool = False,
    providers: Optional[str] = None,
    timeout_ms: int = 2000,
):
    # Return cached health info populated at startup; lazily build if missing (e.g., in tests)
    global HEALTH_INFO
    if not HEALTH_INFO:
        HEALTH_INFO = _build_health_info()
    if live:
        env = dict(os.environ)
        base_providers = HEALTH_INFO.get("llm_providers", {})
        targets = [p.strip() for p in providers.split(",") if p.strip()] if providers else None
        live_info = _live_connectivity(env, base_providers, targets=targets, timeout_ms=timeout_ms)
        # Non-destructive: return a combined view without mutating the cache
        return {**HEALTH_INFO, "live": live_info}
    return HEALTH_INFO


# Basic JSON error handling
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc),
        },
    )


# Mount static files directory to serve icons and other assets
app.mount("/static", StaticFiles(directory="src/static"), name="static")


# Serve favicon.ico (and fallback to favicon.png if .ico is missing)
@app.get("/favicon.ico")
async def favicon():
    path = os.path.join("src", "static", "favicon.ico")
    if os.path.exists(path):
        return FileResponse(path, media_type="image/x-icon")
    png_path = os.path.join("src", "static", "favicon.png")
    if os.path.exists(png_path):
        return FileResponse(png_path, media_type="image/png")
    return JSONResponse(status_code=404, content={"error": "favicon not found"})
