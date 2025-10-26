"""Tests for tool availability checker."""

import pytest
from gphotos_321sync.media_scanner.tool_checker import check_tool_availability


class TestCheckToolAvailability:
    """Tests for check_tool_availability function."""
    
    def test_returns_dict(self):
        """Test that check_tool_availability returns a dictionary."""
        result = check_tool_availability()
        assert isinstance(result, dict)
    
    def test_checks_expected_tools(self):
        """Test that all expected tools are checked."""
        result = check_tool_availability()
        assert 'ffprobe' in result
        assert 'exiftool' in result
    
    def test_returns_boolean_values(self):
        """Test that all values are booleans."""
        result = check_tool_availability()
        for tool, available in result.items():
            assert isinstance(available, bool)
    
    def test_tool_names_are_strings(self):
        """Test that all tool names are strings."""
        result = check_tool_availability()
        for tool_name in result.keys():
            assert isinstance(tool_name, str)
            assert len(tool_name) > 0
    
    def test_result_is_not_empty(self):
        """Test that the result dictionary is not empty."""
        result = check_tool_availability()
        assert len(result) > 0
    
    def test_consistent_results(self):
        """Test that multiple calls return consistent results."""
        result1 = check_tool_availability()
        result2 = check_tool_availability()
        
        assert result1 == result2
    
    def test_ffprobe_detection(self):
        """Test ffprobe tool detection."""
        result = check_tool_availability()
        assert 'ffprobe' in result
        
        # ffprobe should be available if FFmpeg is installed
        # We can't guarantee it's installed in all test environments,
        # so we just verify the key exists and value is boolean
        assert isinstance(result['ffprobe'], bool)
    
    def test_exiftool_detection(self):
        """Test exiftool detection."""
        result = check_tool_availability()
        assert 'exiftool' in result
        
        # exiftool should be available if ExifTool is installed
        # We can't guarantee it's installed in all test environments,
        # so we just verify the key exists and value is boolean
        assert isinstance(result['exiftool'], bool)
    
    def test_no_none_values(self):
        """Test that no values are None."""
        result = check_tool_availability()
        for tool, available in result.items():
            assert available is not None
    
    def test_no_empty_tool_names(self):
        """Test that no tool names are empty strings."""
        result = check_tool_availability()
        for tool_name in result.keys():
            assert tool_name != ""
    
    def test_tool_checker_import(self):
        """Test that tool_checker module can be imported."""
        from gphotos_321sync.media_scanner import tool_checker
        assert tool_checker is not None
        assert hasattr(tool_checker, 'check_tool_availability')
    
    def test_function_is_callable(self):
        """Test that check_tool_availability is callable."""
        assert callable(check_tool_availability)
    
    def test_function_no_arguments(self):
        """Test that check_tool_availability takes no arguments."""
        # Should work without any arguments
        result = check_tool_availability()
        assert isinstance(result, dict)
        
        # Should not accept arguments
        with pytest.raises(TypeError):
            check_tool_availability("some_argument")
    
    def test_result_keys_are_lowercase(self):
        """Test that all tool names are lowercase."""
        result = check_tool_availability()
        for tool_name in result.keys():
            assert tool_name.islower()
    
    def test_result_keys_are_valid_identifiers(self):
        """Test that all tool names are valid Python identifiers."""
        result = check_tool_availability()
        for tool_name in result.keys():
            assert tool_name.isidentifier()
