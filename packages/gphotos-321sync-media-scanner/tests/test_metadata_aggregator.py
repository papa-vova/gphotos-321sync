"""Tests for metadata aggregator."""

import pytest
from pathlib import Path

from gphotos_321sync.media_scanner.metadata.aggregator import (
    aggregate_metadata,
    _aggregate_timestamp,
    _aggregate_gps,
    _parse_timestamp_from_filename
)


def test_aggregate_metadata_all_sources():
    """Test aggregating metadata from all sources."""
    file_path = Path("IMG_20210101_120000.jpg")
    
    json_metadata = {
        'title': 'Sunset Photo',
        'description': 'Beautiful sunset',
        'photoTakenTime': '2021-01-01T12:00:00',
        'geoData': {
            'latitude': 37.7749,
            'longitude': -122.4194
        }
    }
    
    exif_data = {
        'datetime_original': '2021-01-01T11:00:00',
        'camera_make': 'Canon',
        'camera_model': 'EOS 5D',
        'gps_latitude': 40.7128,
        'gps_longitude': -74.0060
    }
    
    video_data = {
        'width': 1920,
        'height': 1080,
        'duration_seconds': 30.5,
        'frame_rate': 30.0
    }
    
    result = aggregate_metadata(file_path, json_metadata, exif_data, video_data)
    
    # Title from JSON
    assert result['title'] == 'Sunset Photo'
    
    # Description from JSON
    assert result['description'] == 'Beautiful sunset'
    
    # Timestamp from JSON (highest priority)
    assert result['capture_timestamp'] == '2021-01-01T12:00:00'
    
    # GPS from JSON (highest priority)
    assert result['google_geo_data_latitude'] == 37.7749
    assert result['google_geo_data_longitude'] == -122.4194
    
    # EXIF GPS stored separately
    assert result['exif_gps_latitude'] == 40.7128
    assert result['exif_gps_longitude'] == -74.0060
    
    # Camera info from EXIF
    assert result['exif_camera_make'] == 'Canon'
    assert result['exif_camera_model'] == 'EOS 5D'
    
    # Video metadata
    assert result['width'] == 1920
    assert result['height'] == 1080
    assert result['duration_seconds'] == 30.5
    assert result['frame_rate'] == 30.0


def test_aggregate_metadata_json_only():
    """Test aggregating with only JSON metadata."""
    file_path = Path("photo.jpg")
    
    json_metadata = {
        'title': 'My Photo',
        'photoTakenTime': '2021-06-15T14:30:00'
    }
    
    result = aggregate_metadata(file_path, json_metadata, None, None)
    
    assert result['title'] == 'My Photo'
    assert result['capture_timestamp'] == '2021-06-15T14:30:00'
    assert result['exif_camera_make'] is None


def test_aggregate_metadata_exif_only():
    """Test aggregating with only EXIF metadata."""
    file_path = Path("photo.jpg")
    
    exif_data = {
        'datetime_original': '2021-06-15T14:30:00',
        'camera_make': 'Nikon',
        'width': 800,
        'height': 600
    }
    
    result = aggregate_metadata(file_path, None, exif_data, None)
    
    # Title from filename
    assert result['title'] == 'photo'
    
    # Timestamp from EXIF
    assert result['capture_timestamp'] == '2021-06-15T14:30:00'
    
    # Camera from EXIF
    assert result['exif_camera_make'] == 'Nikon'
    
    # Dimensions from EXIF
    assert result['width'] == 800
    assert result['height'] == 600


def test_aggregate_metadata_no_sources():
    """Test aggregating with no metadata sources."""
    file_path = Path("IMG_001.jpg")
    
    result = aggregate_metadata(file_path, None, None, None)
    
    # Title from filename
    assert result['title'] == 'IMG_001'
    
    # No timestamp
    assert result['capture_timestamp'] is None
    
    # No other metadata
    assert result['exif_camera_make'] is None
    assert result['width'] is None


def test_timestamp_precedence():
    """Test timestamp precedence: JSON > EXIF > filename."""
    file_path = Path("IMG_20210101_120000.jpg")
    
    json_metadata = {
        'photoTakenTime': '2021-06-01T10:00:00'
    }
    
    exif_data = {
        'datetime_original': '2021-05-01T09:00:00'
    }
    
    # JSON has highest priority
    result = _aggregate_timestamp(json_metadata, exif_data, file_path)
    assert result == '2021-06-01T10:00:00'
    
    # EXIF when no JSON
    result = _aggregate_timestamp({}, exif_data, file_path)
    assert result == '2021-05-01T09:00:00'
    
    # Filename when no JSON or EXIF
    result = _aggregate_timestamp({}, {}, file_path)
    assert result == '2021-01-01T12:00:00'


def test_gps_precedence():
    """Test GPS precedence: JSON > EXIF."""
    json_metadata = {
        'geoData': {
            'latitude': 37.7749,
            'longitude': -122.4194
        }
    }
    
    exif_data = {
        'gps_latitude': 40.7128,
        'gps_longitude': -74.0060
    }
    
    # JSON has priority
    result = _aggregate_gps(json_metadata, exif_data)
    assert result['google_geo_data_latitude'] == 37.7749
    assert result['google_geo_data_longitude'] == -122.4194
    
    # EXIF GPS is stored separately (not in google_geo_data_*)
    result = _aggregate_gps({}, exif_data)
    assert result['google_geo_data_latitude'] is None


def test_parse_timestamp_from_filename_img_pattern():
    """Test parsing IMG_YYYYMMDD_HHMMSS pattern."""
    result = _parse_timestamp_from_filename("IMG_20210615_143022.jpg")
    assert result == "2021-06-15T14:30:22"


def test_parse_timestamp_from_filename_vid_pattern():
    """Test parsing VID_YYYYMMDD_HHMMSS pattern."""
    result = _parse_timestamp_from_filename("VID_20210615_143022.mp4")
    assert result == "2021-06-15T14:30:22"


def test_parse_timestamp_from_filename_simple_pattern():
    """Test parsing YYYYMMDD_HHMMSS pattern."""
    result = _parse_timestamp_from_filename("20210615_143022.jpg")
    assert result == "2021-06-15T14:30:22"


def test_parse_timestamp_from_filename_date_only():
    """Test parsing YYYY-MM-DD pattern."""
    result = _parse_timestamp_from_filename("2021-06-15.jpg")
    assert result == "2021-06-15T00:00:00"


def test_parse_timestamp_from_filename_no_match():
    """Test filename with no timestamp pattern."""
    result = _parse_timestamp_from_filename("random_photo.jpg")
    assert result is None


def test_dimensions_video_priority():
    """Test that video dimensions take priority over EXIF."""
    file_path = Path("video.mp4")
    
    exif_data = {
        'width': 800,
        'height': 600
    }
    
    video_data = {
        'width': 1920,
        'height': 1080
    }
    
    result = aggregate_metadata(file_path, None, exif_data, video_data)
    
    # Video dimensions should win
    assert result['width'] == 1920
    assert result['height'] == 1080


def test_video_only_fields():
    """Test that video-only fields are None for images."""
    file_path = Path("photo.jpg")
    
    exif_data = {
        'width': 800,
        'height': 600
    }
    
    result = aggregate_metadata(file_path, None, exif_data, None)
    
    assert result['duration_seconds'] is None
    assert result['frame_rate'] is None
