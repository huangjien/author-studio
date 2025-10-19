import asyncio
import importlib

import pytest


def test_parse_keys_from_file_empty_returns_empty(tmp_path):
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("\n\n\n")
    import src.api.security as sec

    importlib.reload(sec)
    assert sec._parse_keys_from_file(str(empty_file)) == []


def test_parse_keys_from_file_json_dict_with_nonlist_keys_fallback(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"keys": "not-a-list"}\nalpha\nbeta')
    import src.api.security as sec

    importlib.reload(sec)
    # Since JSON dict has keys not a list, parser should fallback to newline parsing
    assert sec._parse_keys_from_file(str(bad)) == ['{"keys": "not-a-list"}', "alpha", "beta"]


def test_parse_keys_from_file_json_string_fallback(tmp_path):
    # JSON that parses but is not a list/dict should fall back to newline parsing
    f = tmp_path / "str.json"
    f.write_text('"foo"\nbar')
    import src.api.security as sec

    importlib.reload(sec)
    assert sec._parse_keys_from_file(str(f)) == ['"foo"', "bar"]


def test_env_fingerprint_mtime_success(monkeypatch, tmp_path):
    f = tmp_path / "keys.txt"
    f.write_text("a\n")
    monkeypatch.setenv("API_KEYS_FILE", str(f))
    import src.api.security as sec

    importlib.reload(sec)
    single, multi, file_path, mtime = sec._env_fingerprint()
    assert file_path == str(f)
    assert mtime > 0.0


def test_get_allowed_keys_combined_sources(monkeypatch, tmp_path):
    # Set all sources and ensure union is computed
    monkeypatch.setenv("API_KEY", "one")
    monkeypatch.setenv("API_KEYS", "two, three , two")
    file_path = tmp_path / "keys.txt"
    file_path.write_text("three\nfour\n")
    monkeypatch.setenv("API_KEYS_FILE", str(file_path))

    import src.api.security as sec

    importlib.reload(sec)

    allowed = sec._get_allowed_keys()
    assert allowed == {"one", "two", "three", "four"}


def test_negative_ttl_behaves_as_uncached(monkeypatch, tmp_path):
    # Negative TTL should cause rebuild on each call
    monkeypatch.setenv("API_KEYS_TTL", "-1")
    f = tmp_path / "keys.txt"
    f.write_text("alpha\n")
    monkeypatch.setenv("API_KEYS_FILE", str(f))
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)

    import src.api.security as sec

    importlib.reload(sec)

    # initial key works
    asyncio.run(sec.verify_api_key("alpha"))
    # change file and verify new key is required immediately
    f.write_text("beta\n")
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        asyncio.run(sec.verify_api_key("alpha"))
    asyncio.run(sec.verify_api_key("beta"))


def test_get_allowed_keys_ttl_cached_but_empty(monkeypatch):
    # When no keys are configured, even with positive TTL and unexpired cache,
    # _get_allowed_keys should rebuild instead of returning cached empty set.
    monkeypatch.setenv("API_KEYS_TTL", "10")
    # Ensure no sources present
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.delenv("API_KEYS_FILE", raising=False)

    import src.api.security as sec

    importlib.reload(sec)

    # Freeze time so TTL remains unexpired between calls
    t0 = 1_000_000.0
    monkeypatch.setattr(sec, "_now", lambda: t0, raising=True)

    # First call populates cache with empty set and sets expiry
    first = sec._get_allowed_keys()
    assert first == set()

    # Second call at same time should rebuild (since cached is empty) and still return empty
    second = sec._get_allowed_keys()
    assert second == set()


def test_api_keys_env_ignores_empty_tokens(monkeypatch):
    monkeypatch.setenv("API_KEYS", "alpha, , , beta, , ")
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("API_KEYS_FILE", raising=False)
    import src.api.security as sec

    importlib.reload(sec)
    allowed = sec._get_allowed_keys()
    assert allowed == {"alpha", "beta"}
