import json
import logging
import os

from src.services.logging import JSONFormatter, init_logging


def test_env_driven_json_and_level(monkeypatch, capsys):
    # Drive init via environment variables
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["LOG_JSON"] = "true"
    init_logging(level=None, json=None)

    logging.getLogger().debug("env_debug")
    captured = capsys.readouterr()
    line = (captured.err or captured.out).strip().splitlines()[-1]
    data = json.loads(line)
    assert data["level"] == "DEBUG"
    assert data["message"] == "env_debug"


def test_json_formatter_exc_info_fallback(monkeypatch, capsys):
    # Use JSON formatter but force formatException to raise to hit fallback path
    init_logging(json=True)

    formatter = None
    for h in logging.getLogger().handlers:
        formatter = h.formatter
        break
    assert isinstance(formatter, JSONFormatter)

    def bad_format_exc_info(exc_info):
        raise RuntimeError("format failure")

    monkeypatch.setattr(formatter, "formatException", bad_format_exc_info, raising=True)

    try:
        raise ValueError("bad")
    except ValueError:
        logging.getLogger().error("boom", exc_info=True)

    captured = capsys.readouterr()
    line = (captured.err or captured.out).strip().splitlines()[-1]
    data = json.loads(line)
    assert data.get("exc_info") == "<unable to format exc_info>"
