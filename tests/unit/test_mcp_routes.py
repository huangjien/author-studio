from pathlib import Path

from fastapi.testclient import TestClient

from src.main import app


def test_mcp_status_default_config():
    client = TestClient(app)
    resp = client.get("/mcp/status")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert "servers" in data
    assert isinstance(data["servers"], list)


def test_mcp_status_custom_config_path():
    client = TestClient(app)
    cfg_path = Path(__file__).resolve().parent.parent.parent / "mcp_servers.json"
    assert cfg_path.exists()
    resp = client.get(f"/mcp/status?config_path={cfg_path}")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data.get("servers"), list)
    # Ensure entries have name/type keys
    if data["servers"]:
        entry = data["servers"][0]
        assert "name" in entry
        assert "type" in entry


def test_mcp_status_ping_true():
    client = TestClient(app)
    resp = client.get("/mcp/status?ping=true")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert "servers" in data
    assert isinstance(data["servers"], list)
    # Entries should contain standard keys regardless of ping flag
    if data["servers"]:
        entry = data["servers"][0]
        assert "name" in entry
        assert "type" in entry
        assert "persistent" in entry
        assert "reachable" in entry
        assert "unreachable_reason" in entry


def test_mcp_tools_default_config():
    client = TestClient(app)
    resp = client.get("/mcp/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert "tools" in data
    assert isinstance(data["tools"], list)
    if data["tools"]:
        entry = data["tools"][0]
        assert "name" in entry
        assert "server" in entry
        assert "type" in entry
