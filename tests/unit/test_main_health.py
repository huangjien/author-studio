from fastapi.testclient import TestClient

from src.main import app


def test_health_endpoint_ok():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    # Enhanced health payload should include providers and agents info
    assert "llm_providers" in data
    assert isinstance(data["llm_providers"], dict)
    assert "agents" in data
    assert isinstance(data["agents"], list)
