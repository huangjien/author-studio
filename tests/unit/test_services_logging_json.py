import json
import logging
from pathlib import Path

import pytest

from src.services.logging import init_logging


@pytest.mark.usefixtures()
def test_json_logging_stream_outputs_json(capsys):
    root = logging.getLogger()
    old_handlers = list(root.handlers)
    old_level = root.level
    try:
        init_logging(level=logging.INFO, json=True)
        logging.getLogger().info(
            "json_stream_test",
            extra={"agent_id": "alpha-bot", "session_id": "sess-1", "tool": "web_search"},
        )
        captured = capsys.readouterr()
        # Logs are typically emitted to stderr
        line = (captured.err or captured.out).strip().splitlines()[-1]
        data = json.loads(line)
        assert data["level"] == "INFO"
        assert data["name"] == "root"
        assert data["message"] == "json_stream_test"
        # Extra fields should be present
        assert data["agent_id"] == "alpha-bot"
        assert data["session_id"] == "sess-1"
        assert data["tool"] == "web_search"
        # Basic metadata
        assert "timestamp" in data
        assert "module" in data
    finally:
        for h in list(root.handlers):
            root.removeHandler(h)
        for h in old_handlers:
            root.addHandler(h)
        root.setLevel(old_level)


@pytest.mark.usefixtures()
def test_json_logging_file_outputs_json(tmp_path: Path):
    root = logging.getLogger()
    old_handlers = list(root.handlers)
    old_level = root.level
    logfile = tmp_path / "app.jsonl"
    try:
        init_logging(level=logging.INFO, logfile=str(logfile), json=True)
        logging.getLogger().info(
            "file_json_test",
            extra={"agent_id": "beta-bot", "session_id": "sess-2"},
        )
        # Ensure file handler flushed
        for h in root.handlers:
            if isinstance(h, logging.FileHandler):
                h.flush()
        content = logfile.read_text().strip()
        assert content, "log file should not be empty"
        line = content.splitlines()[-1]
        data = json.loads(line)
        assert data["message"] == "file_json_test"
        assert data["agent_id"] == "beta-bot"
        assert data["session_id"] == "sess-2"
        assert data["level"] == "INFO"
    finally:
        for h in list(root.handlers):
            root.removeHandler(h)
        for h in old_handlers:
            root.addHandler(h)
        root.setLevel(old_level)
