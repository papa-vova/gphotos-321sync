"""Tests for error classification."""

import pytest
from gphotos_321sync.common import GPSyncError
from gphotos_321sync.media_scanner.errors import (
    ScannerError,
    PermissionDeniedError,
    CorruptedFileError,
    IOError,
    ParseError,
    UnsupportedFormatError,
    ToolNotFoundError,
    classify_error,
)


class TestErrorInheritance:
    """Tests for error class inheritance."""
    
    def test_scanner_error_inherits_from_gpsync_error(self):
        """Test that ScannerError inherits from GPSyncError."""
        error = ScannerError("test")
        assert isinstance(error, GPSyncError)
        assert isinstance(error, ScannerError)
    
    def test_all_errors_inherit_from_scanner_error(self):
        """Test that all specific errors inherit from ScannerError."""
        errors = [
            PermissionDeniedError("test"),
            CorruptedFileError("test"),
            IOError("test"),
            ParseError("test"),
            UnsupportedFormatError("test"),
            ToolNotFoundError("test"),
        ]
        
        for error in errors:
            assert isinstance(error, ScannerError)
            assert isinstance(error, GPSyncError)


class TestClassifyError:
    """Tests for classify_error function."""
    
    def test_classify_permission_denied_error(self):
        """Test classification of PermissionDeniedError."""
        error = PermissionDeniedError("Access denied")
        assert classify_error(error) == 'permission'
    
    def test_classify_corrupted_file_error(self):
        """Test classification of CorruptedFileError."""
        error = CorruptedFileError("File corrupted")
        assert classify_error(error) == 'corrupted'
    
    def test_classify_io_error(self):
        """Test classification of IOError."""
        error = IOError("I/O failed")
        assert classify_error(error) == 'io'
    
    def test_classify_parse_error(self):
        """Test classification of ParseError."""
        error = ParseError("Parse failed")
        assert classify_error(error) == 'parse'
    
    def test_classify_unsupported_format_error(self):
        """Test classification of UnsupportedFormatError."""
        error = UnsupportedFormatError("Format not supported")
        assert classify_error(error) == 'unsupported'
    
    def test_classify_tool_not_found_error(self):
        """Test classification of ToolNotFoundError."""
        error = ToolNotFoundError("Tool missing")
        assert classify_error(error) == 'tool_missing'
    
    def test_classify_builtin_permission_error(self):
        """Test classification of built-in PermissionError."""
        error = PermissionError("Access denied")
        assert classify_error(error) == 'permission'
    
    def test_classify_builtin_os_error(self):
        """Test classification of built-in OSError."""
        error = OSError("OS error")
        assert classify_error(error) == 'io'
    
    def test_classify_builtin_value_error(self):
        """Test classification of built-in ValueError."""
        error = ValueError("Invalid value")
        assert classify_error(error) == 'parse'
    
    def test_classify_unknown_error(self):
        """Test classification of unknown error types."""
        error = RuntimeError("Unknown error")
        assert classify_error(error) == 'unknown'
