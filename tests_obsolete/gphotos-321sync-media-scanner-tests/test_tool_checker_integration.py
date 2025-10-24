"""Integration tests for tool checker with config."""

import pytest
from gphotos_321sync.media_scanner.tool_checker import (
    check_tool_availability,
    check_required_tools,
)
from gphotos_321sync.media_scanner.errors import ToolNotFoundError


class TestCheckRequiredTools:
    """Tests for check_required_tools function."""
    
    def test_disabled_tools_no_error(self):
        """Test that disabled tools don't cause errors even if missing."""
        # Should not raise even if tools are missing
        check_required_tools(use_ffprobe=False, use_exiftool=False)
    
    def test_enabled_tool_available_no_error(self):
        """Test that enabled tools don't cause errors if available."""
        tools = check_tool_availability()
        
        # Only test tools that are actually available
        if tools.get('ffprobe', False):
            check_required_tools(use_ffprobe=True, use_exiftool=False)
        
        if tools.get('exiftool', False):
            check_required_tools(use_ffprobe=False, use_exiftool=True)
    
    def test_enabled_tool_missing_raises_error(self):
        """Test that enabled tools raise error if missing."""
        tools = check_tool_availability()
        
        # Test ffprobe
        if not tools.get('ffprobe', False):
            with pytest.raises(ToolNotFoundError) as exc_info:
                check_required_tools(use_ffprobe=True, use_exiftool=False)
            assert 'ffprobe' in str(exc_info.value).lower()
        
        # Test exiftool
        if not tools.get('exiftool', False):
            with pytest.raises(ToolNotFoundError) as exc_info:
                check_required_tools(use_ffprobe=False, use_exiftool=True)
            assert 'exiftool' in str(exc_info.value).lower()
    
    def test_both_enabled_both_missing_raises_error(self):
        """Test that first missing tool raises error when both enabled."""
        tools = check_tool_availability()
        
        # Only test if at least one tool is missing
        if not tools.get('ffprobe', False) or not tools.get('exiftool', False):
            with pytest.raises(ToolNotFoundError):
                check_required_tools(use_ffprobe=True, use_exiftool=True)
