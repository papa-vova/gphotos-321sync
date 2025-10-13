"""Extraction-specific errors."""

from gphotos_321sync.common import GPSyncError


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
