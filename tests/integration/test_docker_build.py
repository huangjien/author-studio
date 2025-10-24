import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGE_NAME = "ai-agent-app"


def docker_available():
    return shutil.which("docker") is not None


@pytest.mark.skipif(not docker_available(), reason="Docker not available")
@pytest.mark.skipif(
    os.getenv("RUN_DOCKER_TESTS") != "1",
    reason="Set RUN_DOCKER_TESTS=1 to run docker tests",
)
def test_docker_build_succeeds():
    # Ensure Dockerfile exists
    dockerfile = REPO_ROOT / "docker" / "studio.Dockerfile"
    assert dockerfile.exists(), "studio.Dockerfile is missing"

    # Build the Docker image using the new Dockerfile location
    cmd = [
        "docker",
        "build",
        "-f",
        str(dockerfile),
        "-t",
        IMAGE_NAME,
        ".",
    ]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
    assert proc.returncode == 0, "Docker build failed"