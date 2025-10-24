"""Base error definitions for gphotos_321sync packages."""

from typing import Any, Dict


class GPSyncError(Exception):
    """Base exception for all gphotos_321sync errors."""

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context: Dict[str, Any] = context


class FileProcessingError(GPSyncError):
    """Base exception for file processing errors."""
    pass


class PermissionDeniedError(FileProcessingError):
    """File access denied due to permissions."""
    pass


class CorruptedFileError(FileProcessingError):
    """File is corrupted or malformed."""
    pass


class UnsupportedFormatError(FileProcessingError):
    """File format is not supported."""
    pass


class ToolNotFoundError(FileProcessingError):
    """Required external tool is not available."""
    pass


class ParseError(FileProcessingError):
    """Error parsing file metadata."""
    pass
