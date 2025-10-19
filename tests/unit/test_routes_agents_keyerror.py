import asyncio
import importlib

import pytest


def test_invoke_route_keyerror_returns_404(monkeypatch):
    # Import route function directly to hit the KeyError except branch
    from src.api.routes.agents import InvokeRequest, invoke
    from src.services import agent_service as agent_service_module

    importlib.reload(agent_service_module)

    def missing(*args, **kwargs):
        raise KeyError("missing")

    monkeypatch.setattr(
        agent_service_module,
        "invoke_agent",
        missing,
        raising=True,
    )

    class DummyRequest:
        headers = {"Accept-Language": "en"}

    body = InvokeRequest(input="Hello")

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        asyncio.run(invoke("alpha-bot", DummyRequest(), body))
    assert exc.value.status_code == 404
