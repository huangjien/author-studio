import json
import logging
import sys

from src.services.logging import JSONFormatter, init_logging


def test_init_logging_adds_file_handler_and_json_format(tmp_path):
    logfile = tmp_path / "app.log"
    init_logging(level=None, logfile=str(logfile), json=True)
    logger = logging.getLogger("test")
    logger.info("hello", extra={"session_id": "s1"})
    # Ensure logfile contains JSON log lines
    with open(logfile, "r") as f:
        contents = f.read().strip()
    assert contents
    payload = json.loads(contents.splitlines()[-1])
    assert payload["level"] == "INFO"
    assert payload["session_id"] == "s1"
    assert payload["message"] == "hello"


def test_json_formatter_includes_exc_info():
    fmt = JSONFormatter()
    try:
        raise ValueError("bad value")
    except Exception:
        logger = logging.getLogger("exc")
        record = logger.makeRecord(
            name=logger.name,
            level=logging.ERROR,
            fn="x.py",
            lno=10,
            msg="oops",
            args=(),
            exc_info=sys.exc_info(),
        )
        out = fmt.format(record)
        data = json.loads(out)
        assert data["level"] == "ERROR"
        assert "exc_info" in data
        assert "ValueError" in data["exc_info"]


def test_init_logging_env_level_invalid_falls_back_to_info(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "notalevel")
    init_logging(level=None, logfile=None, json=False)
    logger = logging.getLogger()
    # Root level should be INFO fallback
    assert logger.level == logging.INFO
