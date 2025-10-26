"""Tests for error classification and handling."""

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
    
    def test_error_message_preservation(self):
        """Test that error messages are preserved."""
        message = "Test error message"
        error = ScannerError(message)
        assert str(error) == message
        
        specific_error = PermissionDeniedError(message)
        assert str(specific_error) == message


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
    
    def test_classify_builtin_key_error(self):
        """Test classification of built-in KeyError."""
        error = KeyError("Missing key")
        assert classify_error(error) == 'parse'
    
    def test_classify_builtin_attribute_error(self):
        """Test classification of built-in AttributeError."""
        error = AttributeError("Missing attribute")
        assert classify_error(error) == 'parse'
    
    def test_classify_unknown_error(self):
        """Test classification of unknown error types."""
        error = RuntimeError("Unknown error")
        assert classify_error(error) == 'unknown'
    
    def test_classify_none_error(self):
        """Test classification of None (should not happen in practice)."""
        # This should not happen in practice, but test robustness
        assert classify_error(None) == 'unknown'


class TestErrorCategories:
    """Tests for error category consistency."""
    
    def test_error_categories_match_database_schema(self):
        """Test that error categories match database schema constraints."""
        # These categories should match the CHECK constraint in the database schema
        expected_categories = {
            'permission_denied',
            'corrupted', 
            'io_error',
            'parse_error',
            'unsupported_format'
        }
        
        # Test that our classification function returns valid categories
        test_cases = [
            (PermissionDeniedError("test"), 'permission'),
            (CorruptedFileError("test"), 'corrupted'),
            (IOError("test"), 'io'),
            (ParseError("test"), 'parse'),
            (UnsupportedFormatError("test"), 'unsupported'),
        ]
        
        for error, expected_category in test_cases:
            actual_category = classify_error(error)
            # Map our internal categories to database categories
            category_mapping = {
                'permission': 'permission_denied',
                'corrupted': 'corrupted',
                'io': 'io_error',
                'parse': 'parse_error',
                'unsupported': 'unsupported_format',
                'tool_missing': 'unsupported_format',  # Tool missing maps to unsupported
                'unknown': 'parse_error'  # Unknown maps to parse_error as fallback
            }
            
            db_category = category_mapping.get(actual_category, 'parse_error')
            assert db_category in expected_categories
    
    def test_error_category_completeness(self):
        """Test that all error types have valid categories."""
        error_types = [
            PermissionDeniedError,
            CorruptedFileError,
            IOError,
            ParseError,
            UnsupportedFormatError,
            ToolNotFoundError,
        ]
        
        valid_categories = {
            'permission', 'corrupted', 'io', 'parse', 
            'unsupported', 'tool_missing', 'unknown'
        }
        
        for error_type in error_types:
            error = error_type("test")
            category = classify_error(error)
            assert category in valid_categories


class TestErrorHandlingIntegration:
    """Integration tests for error handling."""
    
    def test_error_chaining(self):
        """Test that errors can be chained properly."""
        try:
            try:
                raise PermissionError("Low level permission error")
            except PermissionError as e:
                raise PermissionDeniedError("High level permission error") from e
        except PermissionDeniedError as e:
            assert isinstance(e, ScannerError)
            assert isinstance(e, GPSyncError)
            assert classify_error(e) == 'permission'
    
    def test_error_context_preservation(self):
        """Test that error context is preserved through classification."""
        error_msg = "File '/path/to/file.jpg' could not be read"
        error = CorruptedFileError(error_msg)
        
        category = classify_error(error)
        assert category == 'corrupted'
        assert error_msg in str(error)
    
    def test_multiple_error_types_same_category(self):
        """Test that multiple error types can map to the same category."""
        # Both PermissionDeniedError and PermissionError should map to 'permission'
        custom_error = PermissionDeniedError("Custom permission error")
        builtin_error = PermissionError("Built-in permission error")
        
        assert classify_error(custom_error) == 'permission'
        assert classify_error(builtin_error) == 'permission'
        
        # Both IOError and OSError should map to 'io'
        custom_io_error = IOError("Custom I/O error")
        builtin_io_error = OSError("Built-in I/O error")
        
        assert classify_error(custom_io_error) == 'io'
        assert classify_error(builtin_io_error) == 'io'


class TestErrorEdgeCases:
    """Tests for error handling edge cases."""
    
    def test_empty_error_message(self):
        """Test handling of empty error messages."""
        error = ScannerError("")
        assert str(error) == ""
        assert classify_error(error) == 'unknown'  # ScannerError maps to unknown
    
    def test_none_error_message(self):
        """Test handling of None error messages."""
        error = ScannerError(None)
        assert str(error) == "None"
        assert classify_error(error) == 'unknown'
    
    def test_very_long_error_message(self):
        """Test handling of very long error messages."""
        long_message = "A" * 10000
        error = CorruptedFileError(long_message)
        
        assert len(str(error)) == 10000
        assert classify_error(error) == 'corrupted'
    
    def test_unicode_error_message(self):
        """Test handling of Unicode error messages."""
        unicode_message = "文件损坏: /path/to/文件.jpg"
        error = CorruptedFileError(unicode_message)
        
        assert str(error) == unicode_message
        assert classify_error(error) == 'corrupted'
    
    def test_nested_exception_handling(self):
        """Test handling of nested exceptions."""
        try:
            try:
                raise ValueError("Inner error")
            except ValueError as e:
                raise ParseError("Outer error") from e
        except ParseError as e:
            assert classify_error(e) == 'parse'
            assert isinstance(e.__cause__, ValueError)
