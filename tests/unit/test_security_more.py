import asyncio
import importlib

import pytest


def test_parse_keys_from_file_nonexistent_returns_empty(monkeypatch):
    import src.api.security as sec

    importlib.reload(sec)
    # Path does not exist should return empty list
    assert sec._parse_keys_from_file("/nonexistent/path/keys.txt") == []


def test_parse_keys_from_file_invalid_json_fallback_newline(tmp_path):
    import src.api.security as sec

    importlib.reload(sec)
    bad = tmp_path / "bad.txt"
    bad.write_text("bad-json-content\nalpha\nbeta\n")
    # Invalid JSON should fall back to newline parsing
    assert sec._parse_keys_from_file(str(bad)) == ["bad-json-content", "alpha", "beta"]


def test_env_fingerprint_handles_missing_file(monkeypatch):
    # Point to a missing file to exercise exception branch in mtime lookup
    monkeypatch.setenv("API_KEYS_FILE", "/nonexistent/path/keys.txt")
    import src.api.security as sec

    importlib.reload(sec)
    single, multi, file_path, mtime = sec._env_fingerprint()
    assert file_path.endswith("keys.txt")
    assert mtime == 0.0


def test_get_allowed_keys_cache_and_ttl_behavior(monkeypatch, tmp_path):
    # Use a file-based key store
    keys_file = tmp_path / "keys.txt"
    keys_file.write_text("first\n")
    monkeypatch.setenv("API_KEYS_FILE", str(keys_file))
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)

    # Start time control
    t0 = 1_000_000.0
    # TTL set to 10
    monkeypatch.setenv("API_KEYS_TTL", "10")
    import src.api.security as sec

    importlib.reload(sec)

    # Freeze mtime so fingerprint remains constant even if file content changes
    monkeypatch.setattr(sec.os.path, "getmtime", lambda _: 12345.0, raising=True)
    # Freeze time
    monkeypatch.setattr(sec, "_now", lambda: t0, raising=True)

    # First read loads 'first'
    asyncio.run(sec.verify_api_key("first"))
    # Change file, but mtime is unchanged so fingerprint is unchanged
    keys_file.write_text("second\n")

    # Within TTL, cached keys should be used -> 'first' remains valid, 'second' not yet
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        asyncio.run(sec.verify_api_key("second"))
    asyncio.run(sec.verify_api_key("first"))

    # Advance time beyond TTL, cache should rebuild and accept 'second'
    monkeypatch.setattr(sec, "_now", lambda: t0 + 11, raising=True)
    asyncio.run(sec.verify_api_key("second"))


def test_verify_api_key_accepts_key_from_file_json_list(monkeypatch, tmp_path):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
    json_file = tmp_path / "keys.json"
    json_file.write_text('["one", "two", "three"]')
    monkeypatch.setenv("API_KEYS_FILE", str(json_file))

    import src.api.security as sec

    importlib.reload(sec)

    # Key from JSON list should pass
    asyncio.run(sec.verify_api_key("two"))

    from fastapi import HTTPException

    # Wrong key should fail
    with pytest.raises(HTTPException):
        asyncio.run(sec.verify_api_key("four"))


def test_get_allowed_keys_immediate_reload_on_env_change(monkeypatch):
    # TTL positive but env fingerprint change should rebuild immediately
    monkeypatch.setenv("API_KEYS_TTL", "10")
    monkeypatch.setenv("API_KEY", "first")
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.delenv("API_KEYS_FILE", raising=False)

    import src.api.security as sec

    importlib.reload(sec)

    # Initial key works
    asyncio.run(sec.verify_api_key("first"))

    # Change single key in env; fingerprint changes, so new key should be accepted immediately
    monkeypatch.setenv("API_KEY", "second")
    asyncio.run(sec.verify_api_key("second"))


def test_ttl_invalid_string_falls_back_to_default(monkeypatch, tmp_path):
    # Invalid TTL should not crash and should behave like default TTL
    monkeypatch.setenv("API_KEYS_TTL", "bad")
    keys_file = tmp_path / "keys.txt"
    keys_file.write_text("alpha\n")
    monkeypatch.setenv("API_KEYS_FILE", str(keys_file))
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)

    import src.api.security as sec

    importlib.reload(sec)

    # Should accept the key despite bad TTL value
    asyncio.run(sec.verify_api_key("alpha"))


def test_verify_api_key_missing_header_rejected_when_keys_present(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    import src.api.security as sec

    importlib.reload(sec)

    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        asyncio.run(sec.verify_api_key(None))
