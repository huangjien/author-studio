import os
import importlib
import asyncio
import pytest


def test_verify_api_key_allows_when_env_unset(monkeypatch):
    # Ensure API_KEY not set
    monkeypatch.delenv("API_KEY", raising=False)
    import src.api.security as sec
    importlib.reload(sec)

    # Should allow when expected is empty
    asyncio.run(sec.verify_api_key(None))


def test_verify_api_key_rejects_wrong_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    import src.api.security as sec
    importlib.reload(sec)

    with pytest.raises(Exception) as exc:
        asyncio.run(sec.verify_api_key("wrong"))
    # FastAPI raises HTTPException
    from fastapi import HTTPException
    assert isinstance(exc.value, HTTPException)
    assert exc.value.status_code == 401


def test_verify_api_key_accepts_correct_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    import src.api.security as sec
    importlib.reload(sec)

    # Matching key should pass
    asyncio.run(sec.verify_api_key("secret"))