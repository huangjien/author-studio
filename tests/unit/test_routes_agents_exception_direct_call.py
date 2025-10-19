import asyncio

import pytest


def test_invoke_route_exception_direct_call(monkeypatch):
    # Import route function directly to ensure coverage hits the specific raise line
    import src.api.routes.agents as routes
    from src.api.routes.agents import InvokeRequest, invoke

    async def boom(*args, **kwargs):
        raise RuntimeError("Kaboom")

    # Patch AutoGen adapter to raise
    monkeypatch.setattr(routes, "run_single_turn_async", boom, raising=True)

    class DummyRequest:
        headers = {"Accept-Language": "en"}

    body = InvokeRequest(input="Hello")

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        asyncio.run(invoke("alpha-bot", DummyRequest(), body))
    assert exc.value.status_code == 500
