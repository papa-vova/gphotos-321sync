"""Base error definitions for gphotos_321sync packages."""

from typing import Any, Dict


class GPSyncError(Exception):
    """Base exception for all gphotos_321sync errors."""

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context: Dict[str, Any] = context
