import importlib
import asyncio
import pytest


def test_invoke_route_exception_direct_call(monkeypatch):
    # Import route function directly to ensure coverage hits the specific raise line
    from src.api.routes.agents import invoke, InvokeRequest
    from src.services import agent_service as agent_service_module
    importlib.reload(agent_service_module)

    def boom(*args, **kwargs):
        raise RuntimeError("Kaboom")

    monkeypatch.setattr(agent_service_module, "invoke_agent", boom, raising=True)

    class DummyRequest:
        headers = {"Accept-Language": "en"}

    body = InvokeRequest(input="Hello")

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        asyncio.run(invoke("alpha-bot", DummyRequest(), body))
    assert exc.value.status_code == 500