import asyncio

import pytest


def test_invoke_route_keyerror_returns_404(monkeypatch):
    # Import route function directly to hit the KeyError except branch
    import src.api.routes.agents as routes
    from src.api.routes.agents import InvokeRequest, invoke

    # Cause a KeyError at the registry lookup stage (outside inner try)
    def missing_agent(*args, **kwargs):
        raise KeyError("missing")

    monkeypatch.setattr(routes.registry, "get_agent", missing_agent, raising=True)

    class DummyRequest:
        headers = {"Accept-Language": "en"}

    body = InvokeRequest(input="Hello")

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        asyncio.run(invoke("alpha-bot", DummyRequest(), body))
    assert exc.value.status_code == 404
