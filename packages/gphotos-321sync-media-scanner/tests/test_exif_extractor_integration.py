"""Integration tests for EXIF extraction with real image files."""

import pytest
import tempfile
from pathlib import Path
from PIL import Image
from PIL.ExifTags import Base as ExifBase
from datetime import datetime

from gphotos_321sync.media_scanner.metadata.exif_extractor import (
    extract_exif,
    extract_resolution
)


class TestExifExtractorIntegration:
    """Integration tests for EXIF extraction with real image data."""
    
    @pytest.fixture
    def image_with_full_exif(self):
        """Create a test image with comprehensive EXIF data."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            temp_path = Path(f.name)
        
        # Create image
        img = Image.new('RGB', (1920, 1080), color='blue')
        
        # Create EXIF data
        exif = Image.Exif()
        
        # Camera info
        exif[ExifBase.Make] = "Canon"
        exif[ExifBase.Model] = "EOS 5D Mark IV"
        
        # Timestamps
        exif[ExifBase.DateTimeOriginal] = "2021:06:15 14:30:22"
        exif[ExifBase.DateTimeDigitized] = "2021:06:15 14:30:22"
        
        # Exposure settings
        exif[ExifBase.ISOSpeedRatings] = 400
        exif[ExifBase.FNumber] = (28, 10)  # f/2.8
        exif[ExifBase.ExposureTime] = (1, 100)  # 1/100s
        exif[ExifBase.FocalLength] = (50, 1)  # 50mm
        
        # Orientation
        exif[ExifBase.Orientation] = 1
        
        # Save with EXIF
        img.save(temp_path, 'JPEG', exif=exif, quality=95)
        
        yield temp_path
        temp_path.unlink(missing_ok=True)
    
    @pytest.fixture
    def image_with_gps(self):
        """Create a test image with GPS data."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            temp_path = Path(f.name)
        
        # Create image
        img = Image.new('RGB', (800, 600), color='green')
        
        # Create EXIF with GPS using IFDRational
        from PIL.TiffImagePlugin import IFDRational
        
        exif = Image.Exif()
        gps_ifd = exif.get_ifd(0x8825)
        
        # Set GPS coordinates (San Francisco: 37.7749° N, 122.4194° W)
        # GPS coordinates are stored as three separate rationals: degrees, minutes, seconds
        
        # GPSLatitudeRef
        gps_ifd[1] = 'N'
        # GPSLatitude: 37° 46' 29.64" N = (37/1, 46/1, 2964/100)
        gps_ifd[2] = (IFDRational(37, 1), IFDRational(46, 1), IFDRational(2964, 100))
        
        # GPSLongitudeRef
        gps_ifd[3] = 'W'
        # GPSLongitude: 122° 25' 9.84" W = (122/1, 25/1, 984/100)
        gps_ifd[4] = (IFDRational(122, 1), IFDRational(25, 1), IFDRational(984, 100))
        
        # GPSAltitudeRef: 0 = above sea level
        gps_ifd[5] = 0
        # GPSAltitude: 10.5m = 105/10
        gps_ifd[6] = IFDRational(105, 10)
        
        # Save with EXIF
        img.save(temp_path, 'JPEG', exif=exif, quality=95)
        
        yield temp_path
        temp_path.unlink(missing_ok=True)
    
    def test_extract_camera_info(self, image_with_full_exif):
        """Test extracting camera make and model."""
        metadata = extract_exif(image_with_full_exif)
        
        assert metadata['camera_make'] == "Canon"
        assert metadata['camera_model'] == "EOS 5D Mark IV"
    
    def test_extract_timestamps(self, image_with_full_exif):
        """Test extracting EXIF timestamps."""
        metadata = extract_exif(image_with_full_exif)
        
        assert 'datetime_original' in metadata
        assert 'datetime_digitized' in metadata
        
        # Should be in ISO format
        assert 'T' in metadata['datetime_original']
        assert metadata['datetime_original'] == "2021-06-15T14:30:22"
    
    def test_extract_exposure_settings(self, image_with_full_exif):
        """Test extracting exposure settings."""
        metadata = extract_exif(image_with_full_exif)
        
        assert metadata['iso'] == 400
        assert metadata['f_number'] == 2.8
        assert metadata['focal_length'] == 50.0
        assert '1/100' in metadata['exposure_time']
    
    def test_extract_orientation(self, image_with_full_exif):
        """Test extracting orientation."""
        metadata = extract_exif(image_with_full_exif)
        
        assert metadata['orientation'] == 1
    
    def test_extract_gps_coordinates(self, image_with_gps):
        """Test extracting GPS coordinates."""
        metadata = extract_exif(image_with_gps)
        
        assert 'gps_latitude' in metadata
        assert 'gps_longitude' in metadata
        assert 'gps_altitude' in metadata
        
        # Check latitude (should be approximately 37.7749)
        assert 37.7 < metadata['gps_latitude'] < 37.8
        
        # Check longitude (should be approximately -122.4194)
        assert -122.5 < metadata['gps_longitude'] < -122.4
        
        # Check altitude (should be approximately 10.5)
        assert 10.0 < metadata['gps_altitude'] < 11.0
    
    def test_gps_coordinate_conversion(self, image_with_gps):
        """Test that GPS coordinates are converted to decimal correctly."""
        metadata = extract_exif(image_with_gps)
        
        # Verify GPS latitude is positive for North
        assert metadata['gps_latitude'] > 0
        
        # Verify GPS longitude is negative for West
        assert metadata['gps_longitude'] < 0
    
    def test_extract_resolution_from_real_image(self, image_with_full_exif):
        """Test extracting resolution from real image."""
        width, height = extract_resolution(image_with_full_exif)
        
        assert width == 1920
        assert height == 1080
    
    def test_extract_from_png(self):
        """Test EXIF extraction from PNG file."""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            img = Image.new('RGB', (640, 480), color='red')
            img.save(temp_path, 'PNG')
            
            # PNG files typically don't have EXIF
            metadata = extract_exif(temp_path)
            assert isinstance(metadata, dict)
            
            # But resolution should work
            width, height = extract_resolution(temp_path)
            assert width == 640
            assert height == 480
        finally:
            temp_path.unlink(missing_ok=True)
    
    def test_extract_from_image_without_exif(self):
        """Test extracting from image with no EXIF data."""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            # Create image without EXIF
            img = Image.new('RGB', (800, 600), color='yellow')
            img.save(temp_path, 'JPEG', quality=95)
            
            metadata = extract_exif(temp_path)
            
            # Should return empty or minimal dict
            assert isinstance(metadata, dict)
            
            # Resolution should still work
            width, height = extract_resolution(temp_path)
            assert width == 800
            assert height == 600
        finally:
            temp_path.unlink(missing_ok=True)
    
    
    def test_rational_value_parsing(self, image_with_full_exif):
        """Test that rational EXIF values are parsed correctly."""
        metadata = extract_exif(image_with_full_exif)
        
        # F-number should be parsed from (28, 10) to 2.8
        assert isinstance(metadata['f_number'], float)
        assert metadata['f_number'] == 2.8
        
        # Focal length should be parsed from (50, 1) to 50.0
        assert isinstance(metadata['focal_length'], float)
        assert metadata['focal_length'] == 50.0
