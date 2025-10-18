import logging
from typing import Optional

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def init_logging(level: int = logging.INFO, logfile: Optional[str] = None) -> None:
    logger = logging.getLogger()
    logger.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    stdout = logging.StreamHandler()
    stdout.setFormatter(formatter)
    logger.addHandler(stdout)
    if logfile:
        file_handler = logging.FileHandler(logfile)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
