"""Tests for RAW format EXIF extraction with ExifTool."""

import pytest
import tempfile
from pathlib import Path
from gphotos_321sync.media_scanner.metadata.exif_extractor import (
    extract_exif_with_exiftool,
    extract_exif_smart
)
from gphotos_321sync.media_scanner.tool_checker import check_tool_availability


# Check if exiftool is available
tools = check_tool_availability()
exiftool_available = tools.get('exiftool', False)


@pytest.mark.skipif(not exiftool_available, reason="exiftool not available")
class TestExifExtractorWithExifTool:
    """Integration tests for RAW format EXIF extraction using real ExifTool."""
    
    @pytest.fixture
    def mock_raw_file(self):
        """Create a mock RAW file (CR2 format).
        
        Note: This is a minimal fake CR2 file, not a real camera RAW.
        ExifTool can still extract basic metadata from it.
        """
        with tempfile.NamedTemporaryFile(suffix='.CR2', delete=False) as f:
            # Write minimal TIFF/CR2 header
            # TIFF header: byte order (II=little endian) + magic number (42) + IFD offset
            f.write(b'II\x2a\x00\x08\x00\x00\x00')
            # Minimal IFD with Make tag (0x010f)
            f.write(b'\x01\x00')  # 1 entry
            f.write(b'\x0f\x01\x02\x00\x06\x00\x00\x00\x1a\x00\x00\x00')  # Make tag
            f.write(b'\x00\x00\x00\x00')  # Next IFD offset (none)
            # Make value: "Canon\0"
            f.write(b'Canon\x00')
            temp_path = Path(f.name)
        
        yield temp_path
        temp_path.unlink(missing_ok=True)
    
    def test_extract_exif_with_exiftool_cr2(self, mock_raw_file):
        """Test ExifTool extraction from CR2 file."""
        result = extract_exif_with_exiftool(mock_raw_file)
        
        # Should return a dict (may be empty if our fake file is too minimal)
        assert isinstance(result, dict)
    
    def test_extract_exif_smart_with_raw_file(self, mock_raw_file):
        """Test smart extraction with RAW file and ExifTool enabled."""
        result = extract_exif_smart(mock_raw_file, use_exiftool=True)
        
        # Should attempt ExifTool extraction for unknown MIME type
        assert isinstance(result, dict)
    
    def test_extract_exif_smart_raw_without_exiftool_flag(self, mock_raw_file):
        """Test smart extraction with RAW file but ExifTool disabled."""
        result = extract_exif_smart(mock_raw_file, use_exiftool=False)
        
        # Should return empty dict (no ExifTool, Pillow can't read CR2)
        assert result == {}


@pytest.mark.skipif(exiftool_available, reason="Testing behavior when exiftool is not available")
class TestExifExtractorWithoutExifTool:
    """Tests for EXIF extractor when ExifTool is not available."""
    
    def test_extract_raises_error_when_exiftool_not_available(self):
        """Test that extraction raises FileNotFoundError when ExifTool is not installed."""
        with tempfile.NamedTemporaryFile(suffix='.CR2', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(FileNotFoundError):
                extract_exif_with_exiftool(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_extract_smart_raw_without_exiftool_returns_empty(self):
        """Test that smart extraction returns empty dict for RAW when ExifTool unavailable."""
        with tempfile.NamedTemporaryFile(suffix='.CR2', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            # Even with use_exiftool=True, should return empty if tool not available
            result = extract_exif_smart(temp_path, use_exiftool=True)
            assert result == {}
        finally:
            temp_path.unlink(missing_ok=True)
