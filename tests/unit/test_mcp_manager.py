from src.services import mcp_manager


class FakeMCP:
    def __init__(self, command: str, args=None, env=None):
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.started = 0
        self.initialized = 0
        self.stopped = False

    def start(self):
        self.started += 1

    def initialize(self, timeout: float | None = None):
        self.initialized += 1

    def stop(self):
        self.stopped = True

    def call_tool(self, tool: str, args_dict: dict, timeout: float | None = None):
        return {"tool": tool, "args": args_dict}


def test_acquire_returns_same_instance(monkeypatch):
    # Patch MCPClient to our fake implementation
    monkeypatch.setattr(mcp_manager, "MCPClient", FakeMCP)
    monkeypatch.setattr(mcp_manager, "MCPClientError", Exception)

    mgr = mcp_manager.MCPClientManager()

    c1 = mgr.acquire(name="serverA", command="cmd")
    c2 = mgr.acquire(name="serverA", command="cmd")

    assert c1 is c2
    assert c1.started == 1  # only started once
    assert c1.initialized >= 1
    assert not c1.stopped


def test_restart_replaces_instance(monkeypatch):
    monkeypatch.setattr(mcp_manager, "MCPClient", FakeMCP)
    monkeypatch.setattr(mcp_manager, "MCPClientError", Exception)

    mgr = mcp_manager.MCPClientManager()

    c1 = mgr.acquire(name="serverB", command="cmd")
    assert not c1.stopped

    c2 = mgr.restart(name="serverB", command="cmd")
    assert c1 is not c2
    assert c1.stopped is True
    assert c2.started == 1
