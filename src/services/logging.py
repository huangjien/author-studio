import logging
import os

DEFAULT_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

LOG_FORMAT = (
    "%(asctime)s %(levelname)s [%(name)s] %(message)s"
)

def init_logging(level: str | None = None) -> None:
    """Initialize application logging with a sane default format and level."""
    log_level = getattr(logging, (level or DEFAULT_LOG_LEVEL), logging.INFO)
    logging.basicConfig(level=log_level, format=LOG_FORMAT)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)