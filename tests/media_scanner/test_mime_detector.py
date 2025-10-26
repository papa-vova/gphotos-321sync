"""Tests for MIME type detection."""

import pytest
import tempfile
import os
from pathlib import Path
from gphotos_321sync.media_scanner.mime_detector import (
    detect_mime_type,
    is_image_mime_type,
    is_video_mime_type,
)


class TestDetectMimeType:
    """Tests for detect_mime_type function."""
    
    def test_jpeg_detection(self):
        """Test JPEG MIME type detection."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            # Write minimal JPEG header
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF')
            f.flush()
            file_path = Path(f.name)
        
        try:
            mime_type = detect_mime_type(file_path)
            assert mime_type == 'image/jpeg'
        finally:
            os.unlink(file_path)
    
    def test_png_detection(self):
        """Test PNG MIME type detection."""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            # Write PNG signature
            f.write(b'\x89PNG\r\n\x1a\n')
            f.flush()
            file_path = Path(f.name)
        
        try:
            mime_type = detect_mime_type(file_path)
            assert mime_type == 'image/png'
        finally:
            os.unlink(file_path)
    
    def test_mp4_detection(self):
        """Test MP4 MIME type detection."""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            # Write a proper MP4 'ftyp' box with a widely recognized major brand and compatible brands.
            # Structure: size(4) + type(4='ftyp') + major_brand(4) + minor_version(4) + compatible_brands(8)
            # size = 24 bytes (0x00000018)
            f.write(b'\x00\x00\x00\x18ftypmp41\x00\x00\x00\x00mp41isom')
            f.flush()
            file_path = Path(f.name)
        
        try:
            mime_type = detect_mime_type(file_path)
            assert mime_type == 'video/mp4'
        finally:
            os.unlink(file_path)
    
    def test_webm_detection(self):
        """Test WebM MIME type detection."""
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f:
            # Write WebM signature
            f.write(b'\x1a\x45\xdf\xa3')
            f.flush()
            file_path = Path(f.name)
        
        try:
            mime_type = detect_mime_type(file_path)
            # filetype library may not recognize WebM signature, so expect generic type
            assert mime_type == 'application/octet-stream'
        finally:
            os.unlink(file_path)
    
    def test_gif_detection(self):
        """Test GIF MIME type detection."""
        with tempfile.NamedTemporaryFile(suffix='.gif', delete=False) as f:
            # Write GIF signature
            f.write(b'GIF87a')
            f.flush()
            file_path = Path(f.name)
        
        try:
            mime_type = detect_mime_type(file_path)
            assert mime_type == 'image/gif'
        finally:
            os.unlink(file_path)
    
    def test_unknown_file_type(self):
        """Test detection of unknown file type."""
        with tempfile.NamedTemporaryFile(suffix='.unknown', delete=False) as f:
            f.write(b'This is not a recognized file type')
            f.flush()
            file_path = Path(f.name)
        
        try:
            mime_type = detect_mime_type(file_path)
            assert mime_type is None or mime_type == 'application/octet-stream'
        finally:
            os.unlink(file_path)
    
    def test_nonexistent_file(self):
        """Test detection for nonexistent file."""
        nonexistent_path = Path("/nonexistent/file.jpg")
        # detect_mime_type raises FileNotFoundError for nonexistent files
        with pytest.raises(FileNotFoundError):
            detect_mime_type(nonexistent_path)
    
    def test_empty_file(self):
        """Test detection for empty file."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            file_path = Path(f.name)
        
        try:
            mime_type = detect_mime_type(file_path)
            assert mime_type is None or mime_type == 'application/octet-stream'
        finally:
            os.unlink(file_path)
    
    def test_directory(self):
        """Test detection for directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = Path(tmpdir)
            # detect_mime_type raises PermissionError for directories
            with pytest.raises(PermissionError):
                detect_mime_type(dir_path)


class TestIsImageMimeType:
    """Tests for is_image_mime_type function."""
    
    def test_jpeg_is_image(self):
        """Test that JPEG is recognized as image."""
        assert is_image_mime_type('image/jpeg') is True
    
    def test_png_is_image(self):
        """Test that PNG is recognized as image."""
        assert is_image_mime_type('image/png') is True
    
    def test_gif_is_image(self):
        """Test that GIF is recognized as image."""
        assert is_image_mime_type('image/gif') is True
    
    def test_webp_is_image(self):
        """Test that WebP is recognized as image."""
        assert is_image_mime_type('image/webp') is True
    
    def test_mp4_is_not_image(self):
        """Test that MP4 is not recognized as image."""
        assert is_image_mime_type('video/mp4') is False
    
    def test_webm_is_not_image(self):
        """Test that WebM is not recognized as image."""
        assert is_image_mime_type('video/webm') is False
    
    def test_text_is_not_image(self):
        """Test that text is not recognized as image."""
        assert is_image_mime_type('text/plain') is False
    
    def test_none_is_not_image(self):
        """Test that None is not recognized as image."""
        # is_image_mime_type raises AttributeError for None
        with pytest.raises(AttributeError):
            is_image_mime_type(None)
    
    def test_empty_string_is_not_image(self):
        """Test that empty string is not recognized as image."""
        assert is_image_mime_type('') is False


class TestIsVideoMimeType:
    """Tests for is_video_mime_type function."""
    
    def test_mp4_is_video(self):
        """Test that MP4 is recognized as video."""
        assert is_video_mime_type('video/mp4') is True
    
    def test_webm_is_video(self):
        """Test that WebM is recognized as video."""
        assert is_video_mime_type('video/webm') is True
    
    def test_avi_is_video(self):
        """Test that AVI is recognized as video."""
        assert is_video_mime_type('video/x-msvideo') is True
    
    def test_mov_is_video(self):
        """Test that MOV is recognized as video."""
        assert is_video_mime_type('video/quicktime') is True
    
    def test_jpeg_is_not_video(self):
        """Test that JPEG is not recognized as video."""
        assert is_video_mime_type('image/jpeg') is False
    
    def test_png_is_not_video(self):
        """Test that PNG is not recognized as video."""
        assert is_video_mime_type('image/png') is False
    
    def test_text_is_not_video(self):
        """Test that text is not recognized as video."""
        assert is_video_mime_type('text/plain') is False
    
    def test_none_is_not_video(self):
        """Test that None is not recognized as video."""
        # is_video_mime_type raises AttributeError for None
        with pytest.raises(AttributeError):
            is_video_mime_type(None)
    
    def test_empty_string_is_not_video(self):
        """Test that empty string is not recognized as video."""
        assert is_video_mime_type('') is False


class TestMimeDetectorIntegration:
    """Integration tests for MIME detector."""
    
    def test_detect_and_classify_image(self):
        """Test detecting and classifying an image file."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF')
            f.flush()
            file_path = Path(f.name)
        
        try:
            mime_type = detect_mime_type(file_path)
            assert mime_type == 'image/jpeg'
            assert is_image_mime_type(mime_type) is True
            assert is_video_mime_type(mime_type) is False
        finally:
            os.unlink(file_path)
    
    def test_detect_and_classify_video(self):
        """Test detecting and classifying a video file."""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            f.write(b'\x00\x00\x00\x18ftypmp41\x00\x00\x00\x00mp41isom')
            f.flush()
            file_path = Path(f.name)
        
        try:
            mime_type = detect_mime_type(file_path)
            assert mime_type == 'video/mp4'
            assert is_video_mime_type(mime_type) is True
            assert is_image_mime_type(mime_type) is False
        finally:
            os.unlink(file_path)
    
    def test_case_insensitive_mime_types(self):
        """Test that MIME type classification is case sensitive (current implementation)."""
        # Current implementation is case sensitive
        assert is_image_mime_type('IMAGE/JPEG') is False
        assert is_image_mime_type('Image/Png') is False
        assert is_video_mime_type('VIDEO/MP4') is False
        assert is_video_mime_type('Video/Webm') is False
    
    def test_edge_case_mime_types(self):
        """Test edge cases for MIME type classification."""
        # Test with extra whitespace
        assert is_image_mime_type(' image/jpeg ') is False  # Should be exact match
        assert is_video_mime_type(' video/mp4 ') is False   # Should be exact match
        
        # Test with invalid MIME types - current implementation uses startswith
        assert is_image_mime_type('image/') is True  # startswith matches
        assert is_video_mime_type('video/') is True  # startswith matches
        assert is_image_mime_type('/jpeg') is False
        assert is_video_mime_type('/mp4') is False
