"""Logging configuration for the application."""

import logging
import sys
from typing import Any

from pythonjsonlogger import jsonlogger

from app.core.config import settings


def setup_logging() -> None:
    """Configure logging for the application."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Create formatter based on format setting
    if settings.log_format.lower() == "json":
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(module)s %(funcName)s %(lineno)d"
        )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Set levels for noisy libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("passlib").setLevel(logging.WARNING)


class RequestContextFilter(logging.Filter):
    """Filter that adds request context to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add request context to log record."""
        # Add any request-specific context here
        # This can be extended to include request_id, user_id, etc.
        return True


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    logger = logging.getLogger(name)
    return logger


class LogContext:
    """Context manager for adding context to logs."""

    def __init__(self, logger: logging.Logger, **context: Any) -> None:
        """Initialize log context."""
        self.logger = logger
        self.context = context
        self.original_extra = logger.extra.copy() if hasattr(logger, "extra") else {}

    def __enter__(self) -> "LogContext":
        """Enter context manager."""
        self.logger.extra.update(self.context)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager."""
        self.logger.extra = self.original_extra.copy()
