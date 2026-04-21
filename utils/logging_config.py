import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# ---- Constants ----
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: int = DEFAULT_LOG_LEVEL,
    log_file: Path | None = None,
    max_bytes: int = 5_000_000,
    backup_count: int = 3,
) -> logging.Logger:
    """
    Configure application-wide logging, called at app startup.

    Args:
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
        log_file: If provided, also logs to this file with rotation
        max_bytes: Max file size before rotating (default 5MB)
        backup_count: Number of backup files to keep

    Returns:
        The root logger for the application
    """

    # Using "decarb" as prefix to keep our logs separate from library logs
    root_logger = logging.getLogger("decarb")
    root_logger.setLevel(level)

    # Clear any existing handlers (prevents duplicate logs on reload)
    root_logger.handlers.clear()

    # Create the formatter (shared by all handlers)
    formatter = logging.Formatter(DEFAULT_LOG_FORMAT, DEFAULT_DATE_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if log_file:
        # Create parent directories if they don't exist
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    The name becomes "decarb.{name}", so if you pass __name__ from
    pages/loads_page.py, you get "decarb.pages.loads_page"

    Usage:
        from utils.logging_config import get_logger
        logger = get_logger(__name__)

        logger.debug("Detailed stuff")
        logger.info("Normal operations")
        logger.warning("Something odd")
        logger.error("Something broke")
    """
    return logging.getLogger(f"decarb.{name}")
