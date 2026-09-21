"""
Core Logging Module

Provides application logger configuration and stream formatting.
"""

import logging
import sys

from app.core.config import settings


def setup_logging() -> logging.Logger:
    """Configure and return the application logger instance."""
    log_level = logging.DEBUG if settings.debug else logging.INFO

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    app_logger = logging.getLogger(settings.app_name)
    app_logger.setLevel(log_level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if not app_logger.handlers:
        app_logger.addHandler(handler)

    return app_logger


logger = setup_logging()
