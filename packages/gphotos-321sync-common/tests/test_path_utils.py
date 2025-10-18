"""Tests for path utilities."""

import pytest
from pathlib import Path
from gphotos_321sync.common import normalize_path


class TestNormalizePath:
    """Tests for normalize_path function."""
    
    def test_forward_slashes(self):
        """Test that backslashes are converted to forward slashes."""
        path = Path(r"C:\Users\test\photos\image.jpg")
        result = normalize_path(path)
        assert '\\' not in result
        assert '/' in result
    
    def test_unicode_normalization(self):
        """Test Unicode NFC normalization."""
        # Create a path with decomposed Unicode (NFD)
        # é can be represented as e + combining acute accent
        path_nfd = Path("café")  # This might be NFD depending on system
        result = normalize_path(path_nfd)
        # Result should be NFC normalized
        assert result == "café"
    
    def test_relative_path(self):
        """Test normalization of relative paths."""
        path = Path("photos/2023/image.jpg")
        result = normalize_path(path)
        assert result == "photos/2023/image.jpg"
