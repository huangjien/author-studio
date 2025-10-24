import asyncio
import importlib

import pytest


def test_verify_api_key_allows_when_env_unset(monkeypatch):
    # Ensure API_KEY not set
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.delenv("API_KEYS_FILE", raising=False)
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


def test_verify_api_key_accepts_key_from_API_KEYS(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("API_KEYS", "alpha, beta , gamma")
    import src.api.security as sec

    importlib.reload(sec)

    # Key from list should pass
    asyncio.run(sec.verify_api_key("beta"))

    # Wrong key should fail
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        asyncio.run(sec.verify_api_key("delta"))


def test_verify_api_key_accepts_key_from_file_json(monkeypatch, tmp_path):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
    json_file = tmp_path / "keys.json"
    json_file.write_text('{"keys": ["one", "two", "three"]}')
    monkeypatch.setenv("API_KEYS_FILE", str(json_file))

    import src.api.security as sec

    importlib.reload(sec)

    # Key from file should pass
    asyncio.run(sec.verify_api_key("two"))

    # Wrong key should fail
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        asyncio.run(sec.verify_api_key("four"))


def test_verify_api_key_accepts_key_from_file_newline(monkeypatch, tmp_path):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
    txt_file = tmp_path / "keys.txt"
    txt_file.write_text("alpha\n\n beta \n gamma \n")
    monkeypatch.setenv("API_KEYS_FILE", str(txt_file))

    import src.api.security as sec

    importlib.reload(sec)

    # Trimmed key from file should pass
    asyncio.run(sec.verify_api_key("beta"))

    # Wrong key should fail
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        asyncio.run(sec.verify_api_key("delta"))


def test_verify_api_key_ttl_zero_forces_reload(monkeypatch, tmp_path):
    # Disable caching so changes are immediately reflected
    monkeypatch.setenv("API_KEYS_TTL", "0")
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)

    keys_file = tmp_path / "keys.txt"
    keys_file.write_text("first\n")
    monkeypatch.setenv("API_KEYS_FILE", str(keys_file))

    import src.api.security as sec

    importlib.reload(sec)

    # First key works
    asyncio.run(sec.verify_api_key("first"))

    # Update file and ensure new key is picked up immediately
    keys_file.write_text("second\n")

    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        asyncio.run(sec.verify_api_key("first"))
    asyncio.run(sec.verify_api_key("second"))