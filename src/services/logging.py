import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}


class JSONFormatter(logging.Formatter):
    """Minimal structured JSON formatter.

    Includes common log metadata and optional extra fields if supplied via
    logging extra dict (e.g., request_id, session_id, agent_id, tool).
    """

    def format(self, record: logging.LogRecord) -> str:
        # Base fields
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        # Common optional extras
        for key in [
            "request_id",
            "session_id",
            "agent_id",
            "tool",
            "path",
            "method",
            "workflow_type",
            "flavor",
        ]:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        # Exception info if present
        if record.exc_info:
            try:
                payload["exc_info"] = self.formatException(record.exc_info)
            except Exception:
                payload["exc_info"] = "<unable to format exc_info>"
        return json.dumps(payload, ensure_ascii=False)


def init_logging(
    level: int = logging.INFO, logfile: Optional[str] = None, json: Optional[bool] = None
) -> None:
    """Initialize root logger.

    - Default text format remains for backward compatibility with tests.
    - Set json=True to enable structured JSON logging.
    - If json is None, respects environment LOG_JSON (true/false).
    - Respects LOG_LEVEL env if level is None.
    """
    # Determine logging level
    lvl = level
    if lvl is None:
        env_level = os.getenv("LOG_LEVEL")
        if env_level:
            try:
                lvl = getattr(logging, env_level.upper())
            except Exception:
                lvl = logging.INFO
        else:
            lvl = logging.INFO

    # Determine formatter type
    use_json = json if json is not None else _env_bool("LOG_JSON", False)
    formatter: logging.Formatter = JSONFormatter() if use_json else logging.Formatter(LOG_FORMAT)

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(lvl)

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    stdout = logging.StreamHandler()
    stdout.setFormatter(formatter)
    logger.addHandler(stdout)

    if logfile:
        file_handler = logging.FileHandler(logfile)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)