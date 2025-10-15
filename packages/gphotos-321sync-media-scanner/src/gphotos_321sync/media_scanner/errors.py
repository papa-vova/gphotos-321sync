"""Error classes for media scanner."""

from gphotos_321sync.common import GPSyncError


class ScannerError(GPSyncError):
    """Base error for media scanner operations."""
    pass


class PermissionDeniedError(ScannerError):
    """File or directory access was denied due to permissions."""
    pass


class CorruptedFileError(ScannerError):
    """File is corrupted or unreadable."""
    pass


class IOError(ScannerError):
    """I/O operation failed."""
    pass


class ParseError(ScannerError):
    """Failed to parse file metadata or content."""
    pass


class UnsupportedFormatError(ScannerError):
    """File format is not supported."""
    pass


class ToolNotFoundError(ScannerError):
    """Required external tool is not available."""
    pass


def classify_error(exception: Exception) -> str:
    """
    Classify an exception into an error category.
    
    Args:
        exception: The exception to classify
        
    Returns:
        Error category string: 'permission', 'corrupted', 'io', 'parse', 
        'unsupported', 'tool_missing', or 'unknown'
    """
    if isinstance(exception, PermissionDeniedError):
        return 'permission'
    elif isinstance(exception, CorruptedFileError):
        return 'corrupted'
    elif isinstance(exception, IOError):
        return 'io'
    elif isinstance(exception, ParseError):
        return 'parse'
    elif isinstance(exception, UnsupportedFormatError):
        return 'unsupported'
    elif isinstance(exception, ToolNotFoundError):
        return 'tool_missing'
    elif isinstance(exception, PermissionError):
        return 'permission'
    elif isinstance(exception, (OSError, IOError)):
        return 'io'
    elif isinstance(exception, (ValueError, KeyError, AttributeError)):
        return 'parse'
    else:
        return 'unknown'
