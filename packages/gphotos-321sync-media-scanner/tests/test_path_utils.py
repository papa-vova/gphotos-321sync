"""Tests for path utilities."""

import pytest
from pathlib import Path
from gphotos_321sync.media_scanner.path_utils import (
    normalize_path,
    is_media_file,
    is_json_sidecar,
)


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


class TestIsMediaFile:
    """Tests for is_media_file function."""
    
    def test_image_extensions(self):
        """Test that image files are recognized."""
        assert is_media_file(Path("photo.jpg"))
        assert is_media_file(Path("photo.JPEG"))
        assert is_media_file(Path("photo.png"))
        assert is_media_file(Path("photo.heic"))
        assert is_media_file(Path("photo.gif"))
    
    def test_video_extensions(self):
        """Test that video files are recognized."""
        assert is_media_file(Path("video.mp4"))
        assert is_media_file(Path("video.MOV"))
        assert is_media_file(Path("video.avi"))
        assert is_media_file(Path("video.mkv"))
    
    def test_non_media_files(self):
        """Test that non-media files are not recognized."""
        assert not is_media_file(Path("document.txt"))
        assert not is_media_file(Path("data.json"))
        assert not is_media_file(Path("script.py"))
    
    def test_case_insensitive(self):
        """Test that extension matching is case-insensitive."""
        assert is_media_file(Path("photo.JPG"))
        assert is_media_file(Path("photo.Jpg"))
        assert is_media_file(Path("video.MP4"))


class TestIsJsonSidecar:
    """Tests for is_json_sidecar function."""
    
    def test_valid_sidecars(self):
        """Test that valid JSON sidecars are recognized."""
        assert is_json_sidecar(Path("IMG_1234.JPG.json"))
        assert is_json_sidecar(Path("video.mp4.json"))
        assert is_json_sidecar(Path("photo.HEIC.json"))
    
    def test_invalid_sidecars(self):
        """Test that invalid JSON files are not recognized as sidecars."""
        assert not is_json_sidecar(Path("metadata.json"))
        assert not is_json_sidecar(Path("config.json"))
        assert not is_json_sidecar(Path("data.txt.json"))
    
    def test_case_insensitive(self):
        """Test that sidecar detection is case-insensitive."""
        assert is_json_sidecar(Path("photo.jpg.json"))
        assert is_json_sidecar(Path("photo.JPG.json"))
        assert is_json_sidecar(Path("photo.Jpg.JSON"))
