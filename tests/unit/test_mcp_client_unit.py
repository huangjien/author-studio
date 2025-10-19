import logging
from types import SimpleNamespace

import pytest

from src.services.mcp_client import MCPClient, MCPClientError


def test_start_failure(monkeypatch):
    import subprocess as sp

    def bad_popen(*args, **kwargs):
        raise RuntimeError("nope")

    monkeypatch.setattr(sp, "Popen", bad_popen, raising=True)

    c = MCPClient(command="echo")
    with pytest.raises(MCPClientError):
        c.start()


def test_stop_handles_wait_timeout(monkeypatch):
    terminated = {"term": False, "kill": False}

    class FakeProc:
        def terminate(self):
            terminated["term"] = True

        def wait(self, timeout=None):
            raise RuntimeError("hang")

        def kill(self):
            terminated["kill"] = True

    c = MCPClient(command="echo")
    c.proc = FakeProc()
    c.stop()
    assert terminated["term"] is True
    assert terminated["kill"] is True


def test_write_message_missing_stdin_raises():
    c = MCPClient(command="echo")
    c.proc = SimpleNamespace(stdin=None)  # simulate missing stdin
    with pytest.raises(MCPClientError):
        c._write_message({"jsonrpc": "2.0"})


def test_request_mismatched_id_raises(monkeypatch):
    c = MCPClient(command="echo")

    def fake_write_message(payload):
        pass

    def fake_read_message(timeout):
        # Return a response with wrong id
        return {"jsonrpc": "2.0", "id": 999, "result": {}}

    monkeypatch.setattr(c, "_write_message", fake_write_message, raising=True)
    monkeypatch.setattr(c, "_read_message", fake_read_message, raising=True)

    with pytest.raises(MCPClientError):
        c._request("initialize", {}, timeout=0.01)


def test_request_error_field_raises(monkeypatch):
    c = MCPClient(command="echo")

    monkeypatch.setattr(c, "_write_message", lambda payload: None, raising=True)
    monkeypatch.setattr(
        c,
        "_read_message",
        lambda timeout: {"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "fail"}},
        raising=True,
    )

    with pytest.raises(MCPClientError):
        c._request("tools/list", {}, timeout=0.01)


def test_request_missing_result_raises(monkeypatch):
    c = MCPClient(command="echo")

    monkeypatch.setattr(c, "_write_message", lambda payload: None, raising=True)
    monkeypatch.setattr(
        c,
        "_read_message",
        lambda timeout: {"jsonrpc": "2.0", "id": 1},
        raising=True,
    )

    with pytest.raises(MCPClientError):
        c._request("tools/call", {"name": "x", "arguments": {}}, timeout=0.01)


def test_initialize_swallows_errors(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    c = MCPClient(command="echo")
    monkeypatch.setattr(c, "_request", lambda *a, **k: (_ for _ in ()).throw(MCPClientError("bad")))
    c.initialize(timeout=0.01)
    assert any("initialize ignored/failed" in rec.message for rec in caplog.records)


def test_list_tools_returns_empty_on_error(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    c = MCPClient(command="echo")
    monkeypatch.setattr(c, "_request", lambda *a, **k: (_ for _ in ()).throw(MCPClientError("bad")))
    data = c.list_tools(timeout=0.01)
    assert data == {}


def test_call_tool_fallback_and_final_error(monkeypatch):
    c = MCPClient(command="echo")
    calls = {"call": 0, "invoke": 0}

    def fake_request(method, params, timeout=0.01):
        if method == "tools/call":
            calls["call"] += 1
            raise MCPClientError("call fail")
        elif method == "tools/invoke":
            calls["invoke"] += 1
            raise MCPClientError("invoke fail")
        return {}

    monkeypatch.setattr(c, "_request", fake_request, raising=True)

    with pytest.raises(MCPClientError):
        c.call_tool("web_search", {"query": "python"}, timeout=0.01)
    assert calls["call"] == 1
    assert calls["invoke"] == 1


def test_call_tool_success_from_invoke(monkeypatch):
    c = MCPClient(command="echo")

    def fake_request(method, params, timeout=0.01):
        if method == "tools/call":
            raise MCPClientError("call fail")
        elif method == "tools/invoke":
            return {"ok": True, "result": 123}
        return {}

    monkeypatch.setattr(c, "_request", fake_request, raising=True)

    res = c.call_tool("fetch", {"url": "https://example.com"}, timeout=0.01)
    assert res == {"ok": True, "result": 123}
