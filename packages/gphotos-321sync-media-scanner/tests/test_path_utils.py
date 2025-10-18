"""Tests for media scanner path utilities."""

import pytest
from pathlib import Path
from gphotos_321sync.media_scanner.path_utils import (
    should_scan_file,
    is_hidden,
)


class TestIsHidden:
    """Tests for is_hidden function."""
    
    def test_unix_hidden_files(self):
        """Test Unix-style hidden files (starting with dot)."""
        assert is_hidden(Path(".hidden"))
        assert is_hidden(Path(".DS_Store"))
        assert is_hidden(Path(".gitignore"))
    
    def test_regular_files_not_hidden(self):
        """Test that regular files are not hidden."""
        assert not is_hidden(Path("photo.jpg"))
        assert not is_hidden(Path("document.txt"))


class TestShouldScanFile:
    """Tests for should_scan_file function."""
    
    def test_regular_files_should_scan(self):
        """Test that regular files should be scanned."""
        # All regular files should be scanned - MIME detection will determine if media
        assert should_scan_file(Path("photo.jpg"))
        assert should_scan_file(Path("video.mp4"))
        assert should_scan_file(Path("IMG_1234"))  # No extension
        assert should_scan_file(Path("document.txt"))  # Wrong extension
        assert should_scan_file(Path("data.json"))
    
    def test_hidden_files_should_skip(self):
        """Test that hidden files are skipped."""
        assert not should_scan_file(Path(".hidden"))
        assert not should_scan_file(Path(".DS_Store"))
        assert not should_scan_file(Path(".gitignore"))
    
    def test_system_files_should_skip(self):
        """Test that system files are skipped."""
        assert not should_scan_file(Path("Thumbs.db"))
        assert not should_scan_file(Path("desktop.ini"))
        assert not should_scan_file(Path("THUMBS.DB"))  # Case insensitive
    
    def test_temp_files_should_skip(self):
        """Test that temporary files are skipped."""
        assert not should_scan_file(Path("temp.tmp"))
        assert not should_scan_file(Path("cache.temp"))
        assert not should_scan_file(Path("backup.bak"))
        assert not should_scan_file(Path("data.cache"))
