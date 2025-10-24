"""Tests to analyze current error handling patterns across packages."""

import pytest
from pathlib import Path
from gphotos_321sync.common.checksums import compute_crc32
from gphotos_321sync.media_scanner.file_processor import process_file_cpu_work


class TestErrorHandlingPatterns:
    """Test current error handling patterns to understand standardization needs."""
    
    def test_common_package_exception_handling(self, tmp_path):
        """Test that common package uses exception-based error handling."""
        nonexistent_file = tmp_path / "nonexistent.txt"
        
        # Common package raises exceptions
        with pytest.raises(OSError):
            compute_crc32(nonexistent_file)
    
    def test_media_scanner_dict_handling(self, tmp_path):
        """Test that media scanner uses dict-based error handling."""
        nonexistent_file = tmp_path / "nonexistent.txt"
        
        # Media scanner returns dict with error info
        result = process_file_cpu_work(nonexistent_file, 0)
        
        assert isinstance(result, dict)
        assert 'success' in result
        assert 'error' in result
        assert 'error_category' in result
        assert result['success'] is False
        assert result['error'] is not None
        assert result['error_category'] is not None
    
    def test_error_categories_consistency(self, tmp_path):
        """Test that error categories are consistent."""
        nonexistent_file = tmp_path / "nonexistent.txt"
        
        result = process_file_cpu_work(nonexistent_file, 0)
        
        # Check that error_category is one of the expected values
        expected_categories = {
            'permission', 'corrupted', 'io', 'parse', 
            'unsupported', 'tool_missing', 'unknown'
        }
        assert result['error_category'] in expected_categories
    
    def test_success_case_structure(self, tmp_path):
        """Test that success cases have consistent structure."""
        # Create a valid test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World")
        
        result = process_file_cpu_work(test_file, test_file.stat().st_size)
        
        assert isinstance(result, dict)
        assert 'success' in result
        assert result['success'] is True
        assert 'error' in result
        assert 'error_category' in result
        # On success, error fields should be None
        assert result['error'] is None
        assert result['error_category'] is None
