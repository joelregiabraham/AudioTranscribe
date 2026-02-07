"""
Logging configuration module.

Provides a centralized logger with both console and rotating file output.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_DIR = Path.home() / ".audio_transcriber" / "logs"
_LOG_FILE = _LOG_DIR / "transcriber.log"
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT = 3
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False


def get_logger(name: str = "transcriber") -> logging.Logger:
    """
    Return a configured logger instance.

    On first call, sets up console + rotating file handlers.
    Subsequent calls return the existing logger hierarchy.

    Args:
        name: Logger name, typically the module's __name__.

    Returns:
        A configured logging.Logger instance.
    """
    global _initialized

    logger = logging.getLogger(name)

    if not _initialized:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)

        # NEW (captures ALL module loggers)
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

        # Console handler — INFO level
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # File handler — DEBUG level, rotating
        file_handler = RotatingFileHandler(
            _LOG_FILE,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        _initialized = True
        root_logger.debug("Logger initialized. Log file: %s", _LOG_FILE)

    return logger
