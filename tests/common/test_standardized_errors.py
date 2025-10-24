"""Tests for standardized error handling."""

import pytest
from gphotos_321sync.common import (
    GPSyncError, FileProcessingError, PermissionDeniedError,
    CorruptedFileError, UnsupportedFormatError, ToolNotFoundError, ParseError
)


class TestStandardizedErrors:
    """Test standardized error types."""
    
    def test_gpsync_error_base(self):
        """Test base GPSyncError functionality."""
        error = GPSyncError("Test error", file_path="/test/path")
        
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.context == {"file_path": "/test/path"}
    
    def test_file_processing_error_inheritance(self):
        """Test FileProcessingError inheritance."""
        error = FileProcessingError("File processing failed", file_path="/test/path")
        
        assert isinstance(error, GPSyncError)
        assert str(error) == "File processing failed"
        assert error.context == {"file_path": "/test/path"}
    
    def test_specific_error_types(self):
        """Test specific error types."""
        # Permission denied
        perm_error = PermissionDeniedError("Access denied", file_path="/test/path")
        assert isinstance(perm_error, FileProcessingError)
        assert isinstance(perm_error, GPSyncError)
        
        # Corrupted file
        corrupt_error = CorruptedFileError("File is corrupted", file_path="/test/path")
        assert isinstance(corrupt_error, FileProcessingError)
        
        # Unsupported format
        format_error = UnsupportedFormatError("Unsupported format", file_path="/test/path")
        assert isinstance(format_error, FileProcessingError)
        
        # Tool not found
        tool_error = ToolNotFoundError("Tool not found", tool_name="exiftool")
        assert isinstance(tool_error, FileProcessingError)
        
        # Parse error
        parse_error = ParseError("Parse failed", file_path="/test/path")
        assert isinstance(parse_error, FileProcessingError)
    
    def test_error_context_preservation(self):
        """Test that error context is preserved."""
        error = PermissionDeniedError(
            "Access denied", 
            file_path="/test/path",
            user="testuser",
            mode="r"
        )
        
        assert error.context["file_path"] == "/test/path"
        assert error.context["user"] == "testuser"
        assert error.context["mode"] == "r"
