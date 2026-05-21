import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: str = "logs/app.log") -> None:
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    log_level = getattr(logging, level.upper(), logging.INFO)

    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(fmt))

    logging.basicConfig(
        level=log_level,
        format=fmt,
        handlers=[logging.StreamHandler(sys.stdout), file_handler],
    )
