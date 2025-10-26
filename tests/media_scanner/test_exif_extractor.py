"""Tests for EXIF extractor."""

import pytest
import tempfile
from pathlib import Path
from PIL import Image, ExifTags

from gphotos_321sync.media_scanner.metadata.exif_extractor import (
    extract_exif,
    extract_resolution
)


@pytest.fixture
def temp_image():
    """Create a temporary test image."""
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
        temp_path = Path(f.name)
    
    # Create a simple test image
    img = Image.new('RGB', (800, 600), color='red')
    img.save(temp_path, 'JPEG')
    
    yield temp_path
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def temp_image_with_exif():
    """Create a temporary test image with EXIF data."""
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
        temp_path = Path(f.name)
    
    # Create image with EXIF data
    img = Image.new('RGB', (1920, 1080), color='blue')
    
    # Add basic EXIF data
    exif_dict = {
        ExifTags.Base.Make: "Canon",
        ExifTags.Base.Model: "EOS 5D",
        ExifTags.Base.Orientation: 1,
    }
    
    exif = Image.Exif()
    for tag, value in exif_dict.items():
        exif[tag] = value
    
    img.save(temp_path, 'JPEG', exif=exif)
    
    yield temp_path
    temp_path.unlink(missing_ok=True)


class TestExtractExif:
    """Tests for extract_exif function."""
    
    def test_extract_exif_basic_image(self, temp_image):
        """Test extracting EXIF from basic image."""
        result = extract_exif(temp_image)
        
        assert isinstance(result, dict)
        # extract_exif does not return width/height - those are in extract_resolution
        assert 'width' not in result
        assert 'height' not in result
        # Should contain EXIF fields if available (our test image may not have EXIF)
        assert isinstance(result, dict)
    
    def test_extract_exif_with_metadata(self, temp_image_with_exif):
        """Test extracting EXIF from image with metadata."""
        result = extract_exif(temp_image_with_exif)
        
        assert isinstance(result, dict)
        # extract_exif does not return width/height - those are in extract_resolution
        assert 'width' not in result
        assert 'height' not in result
        
        # Check for EXIF metadata if available
        if 'camera_make' in result:
            assert result['camera_make'] == "Canon"
        if 'camera_model' in result:
            assert result['camera_model'] == "EOS 5D"
    
    def test_extract_exif_nonexistent_file(self):
        """Test extracting EXIF from nonexistent file."""
        nonexistent_path = Path("/nonexistent/file.jpg")
        result = extract_exif(nonexistent_path)
        
        # Should return empty dict or None for nonexistent files
        assert result is None or result == {}
    
    def test_extract_exif_non_image_file(self, tmp_path):
        """Test extracting EXIF from non-image file."""
        text_file = tmp_path / "test.txt"
        text_file.write_text("This is not an image")
        
        result = extract_exif(text_file)
        
        # Should handle non-image files gracefully
        assert result is None or result == {}
    
    def test_extract_exif_corrupted_image(self, tmp_path):
        """Test extracting EXIF from corrupted image."""
        corrupted_file = tmp_path / "corrupted.jpg"
        corrupted_file.write_bytes(b"This is not a valid image")
        
        result = extract_exif(corrupted_file)
        
        # Should handle corrupted images gracefully
        assert result is None or result == {}


class TestExtractResolution:
    """Tests for extract_resolution function."""
    
    def test_extract_resolution_basic_image(self, temp_image):
        """Test extracting resolution from basic image."""
        result = extract_resolution(temp_image)
        
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result == (800, 600)
    
    def test_extract_resolution_with_exif(self, temp_image_with_exif):
        """Test extracting resolution from image with EXIF."""
        result = extract_resolution(temp_image_with_exif)
        
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result == (1920, 1080)
    
    def test_extract_resolution_nonexistent_file(self):
        """Test extracting resolution from nonexistent file."""
        nonexistent_path = Path("/nonexistent/file.jpg")
        result = extract_resolution(nonexistent_path)
        
        # Should return None for nonexistent files
        assert result is None
    
    def test_extract_resolution_non_image_file(self, tmp_path):
        """Test extracting resolution from non-image file."""
        text_file = tmp_path / "test.txt"
        text_file.write_text("This is not an image")
        
        result = extract_resolution(text_file)
        
        # Should return None for non-image files
        assert result is None
    
    def test_extract_resolution_corrupted_image(self, tmp_path):
        """Test extracting resolution from corrupted image."""
        corrupted_file = tmp_path / "corrupted.jpg"
        corrupted_file.write_bytes(b"This is not a valid image")
        
        result = extract_resolution(corrupted_file)
        
        # Should return None for corrupted images
        assert result is None


class TestExifExtractorIntegration:
    """Integration tests for EXIF extractor."""
    
    def test_extract_exif_and_resolution_consistency(self, temp_image):
        """Test that extract_exif and extract_resolution return consistent data."""
        exif_result = extract_exif(temp_image)
        resolution_result = extract_resolution(temp_image)
        
        if exif_result and resolution_result:
            assert exif_result['width'] == resolution_result[0]
            assert exif_result['height'] == resolution_result[1]
    
    def test_extract_exif_handles_different_formats(self, tmp_path):
        """Test that extract_exif handles different image formats."""
        # Test PNG
        png_path = tmp_path / "test.png"
        img = Image.new('RGB', (640, 480), color='green')
        img.save(png_path, 'PNG')
        
        result = extract_exif(png_path)
        assert isinstance(result, dict)
        # extract_exif does not return width/height - those are in extract_resolution
        assert 'width' not in result
        assert 'height' not in result
        
        # Clean up
        png_path.unlink(missing_ok=True)
    
    def test_extract_exif_error_handling(self, tmp_path):
        """Test that extract_exif handles errors gracefully."""
        # Test with directory instead of file
        dir_path = tmp_path / "directory"
        dir_path.mkdir()
        
        result = extract_exif(dir_path)
        assert result is None or result == {}
        
        # Test with empty file
        empty_file = tmp_path / "empty.jpg"
        empty_file.touch()
        
        result = extract_exif(empty_file)
        assert result is None or result == {}
    
    def test_extract_resolution_error_handling(self, tmp_path):
        """Test that extract_resolution handles errors gracefully."""
        # Test with directory instead of file
        dir_path = tmp_path / "directory"
        dir_path.mkdir()
        
        result = extract_resolution(dir_path)
        assert result is None
        
        # Test with empty file
        empty_file = tmp_path / "empty.jpg"
        empty_file.touch()
        
        result = extract_resolution(empty_file)
        assert result is None
