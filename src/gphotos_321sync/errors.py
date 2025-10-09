"""Application-wide error definitions."""

from typing import Any, Dict


class GPSyncError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context: Dict[str, Any] = context


class ConfigurationError(GPSyncError):
    """Configuration is invalid or missing."""
    pass


class ArchiveError(GPSyncError):
    """Archive processing failed."""
    pass


class ExtractionError(ArchiveError):
    """Failed to extract archive."""
    pass


class CorruptedArchiveError(ArchiveError):
    """Archive is corrupted."""
    pass


class UnsupportedArchiveError(ArchiveError):
    """Archive format is not supported."""
    pass


class ScanError(GPSyncError):
    """File scanning failed."""
    pass


class MetadataError(GPSyncError):
    """Metadata extraction or processing failed."""
    pass


class CorruptedFileError(MetadataError):
    """File is corrupted and cannot be processed."""
    pass


class MissingMetadataError(MetadataError):
    """Required metadata is missing."""
    pass


class DatabaseError(GPSyncError):
    """Database operation failed."""
    pass


class StorageError(GPSyncError):
    """Storage operation failed."""
    pass


class PipelineError(GPSyncError):
    """Pipeline execution failed."""
    pass


class ValidationError(GPSyncError):
    """Data validation failed."""
    pass
