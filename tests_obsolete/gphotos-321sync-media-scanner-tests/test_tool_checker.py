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
