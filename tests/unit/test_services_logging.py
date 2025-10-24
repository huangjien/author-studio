import logging
from pathlib import Path

import pytest

from src.services.logging import LOG_FORMAT, init_logging


@pytest.mark.usefixtures()
def test_init_logging_configures_stream_handler_and_removes_existing_handlers():
    root = logging.getLogger()
    # Snapshot current logger state
    old_handlers = list(root.handlers)
    old_level = root.level
    try:
        # Add a dummy handler to ensure removal logic is exercised
        dummy = logging.StreamHandler()
        root.addHandler(dummy)
        assert any(h is dummy for h in root.handlers)

        # Initialize logging without logfile
        init_logging()

        # Verify level and handlers
        assert root.getEffectiveLevel() == logging.INFO
        handlers = list(root.handlers)
        # Expect exactly one StreamHandler (stdout)
        assert len(handlers) == 1
        assert isinstance(handlers[0], logging.StreamHandler)
        # Verify formatter format is applied
        fmt = handlers[0].formatter._fmt if handlers[0].formatter else None
        assert fmt == LOG_FORMAT
    finally:
        # Restore original logger state
        for h in list(root.handlers):
            root.removeHandler(h)
        for h in old_handlers:
            root.addHandler(h)
        root.setLevel(old_level)


def test_init_logging_with_debug_level_sets_logger_level():
    root = logging.getLogger()
    old_handlers = list(root.handlers)
    old_level = root.level
    try:
        init_logging(level=logging.DEBUG)
        assert root.getEffectiveLevel() == logging.DEBUG
    finally:
        for h in list(root.handlers):
            root.removeHandler(h)
        for h in old_handlers:
            root.addHandler(h)
        root.setLevel(old_level)


def test_init_logging_with_logfile_writes_message(tmp_path: Path):
    root = logging.getLogger()
    old_handlers = list(root.handlers)
    old_level = root.level
    logfile = tmp_path / "app.log"
    try:
        init_logging(level=logging.INFO, logfile=str(logfile))
        # Emit a test log message
        message = "test message to file"
        logging.getLogger().info(message)
        # Ensure file handler flushed
        for h in root.handlers:
            if isinstance(h, logging.FileHandler):
                h.flush()
        # Read the file and verify content
        content = logfile.read_text()
        # The format includes time; assert stable parts
        assert "INFO [root]" in content
        assert message in content
    finally:
        for h in list(root.handlers):
            root.removeHandler(h)
        for h in old_handlers:
            root.addHandler(h)
        root.setLevel(old_level)