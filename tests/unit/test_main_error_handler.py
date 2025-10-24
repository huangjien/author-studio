import asyncio
import json


def test_unhandled_exception_handler_returns_500():
    from starlette.requests import Request

    from src.main import unhandled_exception_handler

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/boom",
        "headers": [],
    }
    request = Request(scope)
    response = asyncio.run(unhandled_exception_handler(request, Exception("boom")))
    assert response.status_code == 500
    body = response.body
    payload = json.loads(body)
    assert payload["error"] == "Internal Server Error"
    assert payload["message"] == "boom"