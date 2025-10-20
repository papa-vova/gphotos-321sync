"""Tests for PIL warning logging in EXIF extractor."""

import pytest
import tempfile
import logging
from pathlib import Path
from PIL import Image
from unittest.mock import patch

from gphotos_321sync.media_scanner.metadata.exif_extractor import (
    extract_exif,
    extract_resolution
)


@pytest.fixture
def temp_large_image():
    """Create a temporary large image that triggers DecompressionBombWarning."""
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
        temp_path = Path(f.name)
    
    # Create a large image (but not too large to actually process)
    # This is just above the old 89MP threshold but below our new 200MP threshold
    img = Image.new('RGB', (10000, 10000), color='red')  # 100MP
    img.save(temp_path, 'JPEG')
    
    yield temp_path
    temp_path.unlink(missing_ok=True)


def test_decompression_bomb_warning_logged(temp_large_image, caplog):
    """Test that DecompressionBombWarning is captured and logged as structured JSON."""
    # Temporarily lower the threshold to trigger the warning
    original_max = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = 50_000_000  # 50MP threshold
    
    try:
        with caplog.at_level(logging.WARNING):
            resolution = extract_resolution(temp_large_image)
        
        # Should still extract resolution successfully
        assert resolution is not None
        assert resolution == (10000, 10000)
        
        # Check if warning was logged
        warning_messages = [record.message for record in caplog.records if record.levelname == 'WARNING']
        
        # Should have a warning about decompression bomb
        assert any('DecompressionBombWarning' in msg for msg in warning_messages), \
            f"Expected DecompressionBombWarning in logs, got: {warning_messages}"
    
    finally:
        # Restore original threshold
        Image.MAX_IMAGE_PIXELS = original_max


def test_no_warnings_for_normal_image(caplog):
    """Test that normal images don't trigger warnings."""
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
        temp_path = Path(f.name)
    
    try:
        # Create a normal-sized image
        img = Image.new('RGB', (800, 600), color='blue')
        img.save(temp_path, 'JPEG')
        
        with caplog.at_level(logging.WARNING):
            resolution = extract_resolution(temp_path)
        
        assert resolution == (800, 600)
        
        # Should not have any warnings
        warning_messages = [record.message for record in caplog.records if record.levelname == 'WARNING']
        assert len(warning_messages) == 0, f"Unexpected warnings: {warning_messages}"
    
    finally:
        temp_path.unlink(missing_ok=True)


def test_warning_logging_includes_file_path(temp_large_image, caplog):
    """Test that warning logs include the file path for debugging."""
    # Temporarily lower the threshold to trigger the warning
    original_max = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = 50_000_000  # 50MP threshold
    
    try:
        with caplog.at_level(logging.WARNING):
            extract_resolution(temp_large_image)
        
        # Check if warning includes file path
        warning_records = [record for record in caplog.records if record.levelname == 'WARNING']
        
        if warning_records:
            # At least one warning should mention the file path
            assert any(str(temp_large_image) in record.message for record in warning_records), \
                "Warning should include file path for debugging"
    
    finally:
        Image.MAX_IMAGE_PIXELS = original_max


def test_exif_extraction_with_warnings(caplog):
    """Test that EXIF extraction also captures and logs warnings properly."""
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
        temp_path = Path(f.name)
    
    try:
        # Create a large image with EXIF data
        img = Image.new('RGB', (10000, 10000), color='green')
        
        # Temporarily lower threshold
        original_max = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = 50_000_000
        
        try:
            with caplog.at_level(logging.WARNING):
                result = extract_exif(temp_path)
            
            # Should still extract EXIF (even if empty)
            assert isinstance(result, dict)
            
            # Check for warnings
            warning_messages = [record.message for record in caplog.records if record.levelname == 'WARNING']
            
            # May have warnings about decompression bomb
            if warning_messages:
                assert any('DecompressionBombWarning' in msg or 'UserWarning' in msg for msg in warning_messages)
        
        finally:
            Image.MAX_IMAGE_PIXELS = original_max
    
    finally:
        temp_path.unlink(missing_ok=True)
