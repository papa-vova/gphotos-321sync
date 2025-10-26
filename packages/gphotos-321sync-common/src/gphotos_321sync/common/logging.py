"""Structured logging utilities."""

import logging
import logging.handlers
import json
import sys
from typing import Any, Dict, Optional
from datetime import datetime
from pathlib import Path


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


class DetailedFormatter(logging.Formatter):
    """Human-readable detailed formatter."""

    def __init__(self) -> None:
        fmt = (
            "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | "
            "%(message)s"
        )
        super().__init__(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")


class SimpleFormatter(logging.Formatter):
    """Simple formatter for console output."""

    def __init__(self) -> None:
        fmt = "%(levelname)-8s | %(name)s | %(message)s"
        super().__init__(fmt=fmt)


def setup_logging(
    level: str = "INFO",
    format: str = "simple",
    log_file: Optional[Path] = None,
    max_file_size_mb: int = 10,
    backup_count: int = 5,
) -> None:
    """Configure logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Format type (simple, detailed, json)
        log_file: Optional log file path
        max_file_size_mb: Max log file size in MB
        backup_count: Number of backup files to keep
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)

    if format == "json":
        console_handler.setFormatter(StructuredFormatter())
    elif format == "detailed":
        console_handler.setFormatter(DetailedFormatter())
    else:
        console_handler.setFormatter(SimpleFormatter())

    root_logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_file_size_mb * 1024 * 1024,
            backupCount=backup_count,
        )

        # Always use structured format for file logs
        file_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get logger with structured logging support."""
    return logging.getLogger(name)


class LogContext:
    """Context manager for adding structured fields to logs."""

    def __init__(self, logger: logging.Logger, **fields: Any) -> None:
        self.logger = logger
        self.fields = fields
        self.old_factory = None

    def __enter__(self) -> "LogContext":
        self.old_factory = logging.getLogRecordFactory()

        def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
            record = self.old_factory(*args, **kwargs)
            if not hasattr(record, "extra_fields"):
                record.extra_fields = {}
            record.extra_fields.update(self.fields)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        logging.setLogRecordFactory(self.old_factory)
