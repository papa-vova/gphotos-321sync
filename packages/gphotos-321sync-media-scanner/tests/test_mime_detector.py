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
            f.write(b'\x00\x00\x00\x18')  # box size = 24 bytes
            f.write(b'ftyp')                 # box type
            f.write(b'mp42')                 # major brand
            f.write(b'\x00\x00\x00\x00') # minor version
            f.write(b'isom')                 # compatible brand 1
            f.write(b'mp42')                 # compatible brand 2
            # Add a small free box to mimic additional atoms (optional)
            f.write(b'\x00\x00\x00\x08')  # size 8
            f.write(b'free')                 # 'free' box
            f.flush()
            file_path = Path(f.name)
        
        try:
            mime_type = detect_mime_type(file_path)
            assert mime_type == 'video/mp4'
        finally:
            os.unlink(file_path)
    
    def test_unknown_extension(self):
        """Test unknown file type returns default."""
        with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as f:
            f.write(b'random data')
            f.flush()
            file_path = Path(f.name)
        
        try:
            mime_type = detect_mime_type(file_path)
            assert mime_type == 'application/octet-stream'
        finally:
            os.unlink(file_path)
    
    def test_case_insensitive_extension(self):
        """Test that extension matching is case-insensitive."""
        with tempfile.NamedTemporaryFile(suffix='.JPG', delete=False) as f:
            f.write(b'\xff\xd8\xff\xe0')
            f.flush()
            file_path = Path(f.name)
        
        try:
            mime_type = detect_mime_type(file_path)
            assert mime_type == 'image/jpeg'
        finally:
            os.unlink(file_path)


class TestMimeTypeCheckers:
    """Tests for MIME type checker functions."""
    
    def test_is_image_mime_type(self):
        """Test image MIME type detection."""
        assert is_image_mime_type('image/jpeg')
        assert is_image_mime_type('image/png')
        assert is_image_mime_type('image/gif')
        assert not is_image_mime_type('video/mp4')
        assert not is_image_mime_type('application/pdf')
    
    def test_is_video_mime_type(self):
        """Test video MIME type detection."""
        assert is_video_mime_type('video/mp4')
        assert is_video_mime_type('video/quicktime')
        assert is_video_mime_type('video/x-matroska')
        assert not is_video_mime_type('image/jpeg')
        assert not is_video_mime_type('application/pdf')


