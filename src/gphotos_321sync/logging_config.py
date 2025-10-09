"""Structured logging configuration."""

import logging
import logging.handlers
import json
import sys
from pathlib import Path
from typing import Any, Dict
from datetime import datetime


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


def setup_logging() -> None:
    """Configure logging based on configuration."""
    from .config import get_config

    config = get_config()

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.logging.level))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler (always stderr for CLI tools)
    if config.logging.enable_console_logging:
        console_handler = logging.StreamHandler(sys.stderr)

        if config.logging.format == "json":
            console_handler.setFormatter(StructuredFormatter())
        elif config.logging.format == "detailed":
            console_handler.setFormatter(DetailedFormatter())
        else:
            console_handler.setFormatter(SimpleFormatter())

        root_logger.addHandler(console_handler)

    # File handler
    if config.logging.enable_file_logging:
        log_file = Path(config.paths.log_directory) / "app.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=config.logging.max_file_size_mb * 1024 * 1024,
            backupCount=config.logging.backup_count,
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
