import os
import shutil
import subprocess
import time
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGE_NAME = "ai-agent-app"
CONTAINER_NAME = "ai-agent-app-test"
PORT = int(os.getenv("DOCKER_TEST_PORT", "8000"))
API_KEY = "test-key"


def docker_available():
    return shutil.which("docker") is not None


@pytest.mark.skipif(not docker_available(), reason="Docker not available")
@pytest.mark.skipif(
    os.getenv("RUN_DOCKER_TESTS") != "1",
    reason="Set RUN_DOCKER_TESTS=1 to run docker tests",
)
def test_docker_run_and_invoke_endpoint():
    # Build image (in case not built yet)
    build_cmd = [
        "docker",
        "build",
        "-f",
        str(REPO_ROOT / "docker" / "studio.Dockerfile"),
        "-t",
        IMAGE_NAME,
        ".",
    ]
    build_proc = subprocess.run(build_cmd, cwd=str(REPO_ROOT))
    assert build_proc.returncode == 0, "Docker build failed"

    # Ensure any previous container is removed
    subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], cwd=str(REPO_ROOT))

    # Run the container with agent_configs mounted and API key provided
    run_cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        CONTAINER_NAME,
        "-p",
        f"{PORT}:8000",
        "-v",
        f"{REPO_ROOT}/agent_configs:/app/agent_configs",
        "-e",
        f"API_KEY={API_KEY}",
        "-e",
        "AGENT_CONFIG_DIR=/app/agent_configs",
        "-e",
        "AGENTS_AUTOGEN_MOCK=1",
        IMAGE_NAME,
    ]
    run_proc = subprocess.run(run_cmd, cwd=str(REPO_ROOT))
    assert run_proc.returncode == 0, "Docker run failed"

    try:
        # Wait briefly for the server to start
        time.sleep(2)

        # Invoke the agent endpoint
        url = f"http://localhost:{PORT}/agents/alpha-bot/invoke"
        headers = {"X-API-Key": API_KEY}
        payload = {"input": "Hello from docker"}
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, headers=headers, json=payload)
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code}, body={resp.text}"
        data = resp.json()
        assert "session_id" in data
        assert "output" in data
        assert "alpha-bot" in data["output"]
    finally:
        # Clean up container
        subprocess.run(["docker", "rm", "-f", CONTAINER_NAME], cwd=str(REPO_ROOT))
