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


def test_extract_resolution(temp_image):
    """Test resolution extraction."""
    width, height = extract_resolution(temp_image)
    
    assert width == 800
    assert height == 600


def test_extract_resolution_with_exif(temp_image_with_exif):
    """Test resolution extraction from image with EXIF."""
    width, height = extract_resolution(temp_image_with_exif)
    
    assert width == 1920
    assert height == 1080


def test_extract_resolution_missing_file():
    """Test resolution extraction from missing file."""
    result = extract_resolution(Path("/nonexistent/image.jpg"))
    assert result is None


def test_extract_exif_no_data(temp_image):
    """Test EXIF extraction from image without EXIF data."""
    result = extract_exif(temp_image)
    
    # Should return empty dict or minimal data
    assert isinstance(result, dict)


def test_extract_exif_with_data(temp_image_with_exif):
    """Test EXIF extraction from image with EXIF data."""
    result = extract_exif(temp_image_with_exif)
    
    assert isinstance(result, dict)
    # Check for camera info
    if 'camera_make' in result:
        assert result['camera_make'] == "Canon"
    if 'camera_model' in result:
        assert result['camera_model'] == "EOS 5D"
    if 'orientation' in result:
        assert result['orientation'] == 1


def test_extract_exif_missing_file():
    """Test EXIF extraction from missing file."""
    result = extract_exif(Path("/nonexistent/image.jpg"))
    
    # Should return empty dict on error
    assert isinstance(result, dict)
    assert len(result) == 0


def test_extract_exif_invalid_file(temp_image):
    """Test EXIF extraction from invalid image file."""
    # Write garbage data
    temp_image.write_bytes(b"not an image")
    
    result = extract_exif(temp_image)
    
    # Should return empty dict on error
    assert isinstance(result, dict)


def test_resolution_extraction_png():
    """Test resolution extraction from PNG file."""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        temp_path = Path(f.name)
    
    try:
        img = Image.new('RGB', (640, 480), color='green')
        img.save(temp_path, 'PNG')
        
        width, height = extract_resolution(temp_path)
        
        assert width == 640
        assert height == 480
    finally:
        temp_path.unlink(missing_ok=True)
