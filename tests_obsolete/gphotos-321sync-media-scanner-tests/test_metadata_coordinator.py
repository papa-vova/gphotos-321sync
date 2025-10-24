"""Tests for metadata coordinator module."""

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone

from gphotos_321sync.media_scanner.metadata_coordinator import (
    coordinate_metadata,
    MediaItemRecord
)
from gphotos_321sync.media_scanner.discovery import FileInfo


@pytest.fixture
def test_file_info(tmp_path):
    """Create test FileInfo."""
    file_path = tmp_path / "test.jpg"
    file_path.write_text("fake image", encoding='utf-8')
    
    return FileInfo(
        file_path=file_path,
        relative_path=Path("Album/test.jpg"),
        album_folder_path=Path("Album"),
        json_sidecar_path=None,
        file_size=100
    )


@pytest.fixture
def test_metadata_ext():
    """Create test metadata extraction result."""
    return {
        'success': True,
        'mime_type': 'image/jpeg',
        'crc32': 'a1b2c3d4',
        'content_fingerprint': 'f' * 64,
        'width': 1920,
        'height': 1080,
        'exif_data': {
            'datetime_original': datetime(2023, 7, 1, 12, 30, 0, tzinfo=timezone.utc),
            'camera_make': 'Canon',
            'camera_model': 'EOS R5',
            'gps': {
                'latitude': 37.7749,
                'longitude': -122.4194,
                'altitude': 10.5
            }
        },
        'video_data': None,
        'error': None
    }


def test_coordinate_metadata_basic(test_file_info, test_metadata_ext):
    """Test basic metadata coordination."""
    record, people_names = coordinate_metadata(
        file_info=test_file_info,
        metadata_ext=test_metadata_ext,
        album_id='album-123',
        scan_run_id='scan-456'
    )
    
    assert record.media_item_id is not None
    assert record.relative_path == "Album/test.jpg"  # normalize_path always returns forward slashes
    assert record.album_id == 'album-123'
    assert record.scan_run_id == 'scan-456'
    assert record.status == 'present'
    assert people_names == []  # No people in basic test


def test_coordinate_metadata_cpu_data(test_file_info, test_metadata_ext):
    """Test that CPU result data is included."""
    record, _ = coordinate_metadata(
        file_info=test_file_info,
        metadata_ext=test_metadata_ext,
        album_id='album-123',
        scan_run_id='scan-456'
    )
    
    assert record.mime_type == 'image/jpeg'
    assert record.crc32 == 'a1b2c3d4'
    assert record.content_fingerprint == 'f' * 64
    assert record.width == 1920
    assert record.height == 1080
    assert record.file_size == 100


def test_coordinate_metadata_exif_data(test_file_info, test_metadata_ext):
    """Test that EXIF data is extracted."""
    record, _ = coordinate_metadata(
        file_info=test_file_info,
        metadata_ext=test_metadata_ext,
        album_id='album-123',
        scan_run_id='scan-456'
    )
    
    assert record.exif_datetime_original == datetime(2023, 7, 1, 12, 30, 0, tzinfo=timezone.utc)
    assert record.exif_camera_make == 'Canon'
    assert record.exif_camera_model == 'EOS R5'
    assert record.exif_gps_latitude == 37.7749
    assert record.exif_gps_longitude == -122.4194
    assert record.exif_gps_altitude == 10.5


def test_coordinate_metadata_with_json_sidecar(tmp_path, test_metadata_ext):
    """Test coordination with JSON sidecar."""
    # Create file with JSON sidecar
    file_path = tmp_path / "test.jpg"
    file_path.write_text("fake image", encoding='utf-8')
    
    json_path = tmp_path / "test.jpg.json"
    json_data = {
        "title": "Summer Vacation",
        "description": "Beach photo",
        "photoTakenTime": {"timestamp": "1688220600"},
        "geoData": {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "altitude": 5.0
        }
    }
    json_path.write_text(json.dumps(json_data), encoding='utf-8')
    
    file_info = FileInfo(
        file_path=file_path,
        relative_path=Path("Album/test.jpg"),
        album_folder_path=Path("Album"),
        json_sidecar_path=json_path,
        file_size=100
    )
    
    record, people_names = coordinate_metadata(
        file_info=file_info,
        metadata_ext=test_metadata_ext,
        album_id='album-123',
        scan_run_id='scan-456'
    )
    
    # JSON metadata should be present
    assert people_names == []  # No people in this test
    assert record.title == "Summer Vacation"
    assert record.google_description == "Beach photo"
    assert record.google_geo_latitude == 40.7128
    assert record.google_geo_longitude == -74.0060
    
    # Sidecar fingerprint should be calculated
    assert record.sidecar_fingerprint is not None
    assert len(record.sidecar_fingerprint) == 64  # SHA-256 hex string


def test_coordinate_metadata_json_parse_error(tmp_path, test_metadata_ext):
    """Test handling of invalid JSON sidecar."""
    # Create file with invalid JSON sidecar
    file_path = tmp_path / "test.jpg"
    file_path.write_text("fake image", encoding='utf-8')
    
    json_path = tmp_path / "test.jpg.json"
    json_path.write_text("invalid json{", encoding='utf-8')
    
    file_info = FileInfo(
        file_path=file_path,
        relative_path=Path("Album/test.jpg"),
        album_folder_path=Path("Album"),
        json_sidecar_path=json_path,
        file_size=100
    )
    
    # Should not raise exception, just log warning
    record, people_names = coordinate_metadata(
        file_info=file_info,
        metadata_ext=test_metadata_ext,
        album_id='album-123',
        scan_run_id='scan-456'
    )
    
    # Should still create record without JSON metadata
    assert isinstance(record, MediaItemRecord)
    assert people_names == []
    assert record.google_description is None


def test_coordinate_metadata_video_data(test_file_info):
    """Test coordination with video metadata."""
    metadata_ext = {
        'success': True,
        'mime_type': 'video/mp4',
        'crc32': 'a1b2c3d4',
        'content_fingerprint': 'f' * 64,
        'width': 1920,
        'height': 1080,
        'exif_data': {},
        'video_data': {
            'duration': 120.5,
            'frame_rate': 30.0,
            'width': 1920,
            'height': 1080
        },
        'error': None
    }
    
    record, _ = coordinate_metadata(
        file_info=test_file_info,
        metadata_ext=metadata_ext,
        album_id='album-123',
        scan_run_id='scan-456'
    )
    
    assert record.duration_seconds == 120.5
    assert record.frame_rate == 30.0


def test_coordinate_metadata_no_video_data(test_file_info, test_metadata_ext):
    """Test coordination without video metadata (image file)."""
    record, _ = coordinate_metadata(
        file_info=test_file_info,
        metadata_ext=test_metadata_ext,
        album_id='album-123',
        scan_run_id='scan-456'
    )
    
    assert record.duration_seconds is None
    assert record.frame_rate is None


def test_coordinate_metadata_minimal_metadata_ext(test_file_info):
    """Test coordination with minimal CPU result."""
    metadata_ext = {
        'success': True,
        'mime_type': 'image/jpeg',
        'crc32': 'a1b2c3d4',
        'content_fingerprint': 'f' * 64,
        'width': None,
        'height': None,
        'exif_data': {},
        'video_data': None,
        'error': None
    }
    
    record, _ = coordinate_metadata(
        file_info=test_file_info,
        metadata_ext=metadata_ext,
        album_id='album-123',
        scan_run_id='scan-456'
    )
    
    assert record.mime_type == 'image/jpeg'
    assert record.width is None
    assert record.height is None
    assert record.exif_camera_make is None


def test_media_item_record_to_dict(test_file_info, test_metadata_ext):
    """Test MediaItemRecord.to_dict() conversion."""
    record, _ = coordinate_metadata(
        file_info=test_file_info,
        metadata_ext=test_metadata_ext,
        album_id='album-123',
        scan_run_id='scan-456'
    )
    
    data = record.to_dict()
    
    assert isinstance(data, dict)
    assert data['relative_path'] == "Album/test.jpg"  # normalize_path always returns forward slashes
    assert data['album_id'] == 'album-123'
    assert data['scan_run_id'] == 'scan-456'
    assert data['mime_type'] == 'image/jpeg'
    assert data['status'] == 'present'


def test_media_item_record_has_media_item_id(test_file_info, test_metadata_ext):
    """Test that MediaItemRecord has a generated media_item_id."""
    record, _ = coordinate_metadata(
        file_info=test_file_info,
        metadata_ext=test_metadata_ext,
        album_id='album-123',
        scan_run_id='scan-456'
    )
    
    assert record.media_item_id is not None
    assert len(record.media_item_id) == 36  # UUID5 format (same length as UUID4)


def test_media_item_record_deterministic_ids(test_file_info, test_metadata_ext):
    """Test that UUID5 generates deterministic IDs for same inputs."""
    record1, _ = coordinate_metadata(
        file_info=test_file_info,
        metadata_ext=test_metadata_ext,
        album_id='album-123',
        scan_run_id='scan-456'
    )
    
    record2, _ = coordinate_metadata(
        file_info=test_file_info,
        metadata_ext=test_metadata_ext,
        album_id='album-123',
        scan_run_id='scan-456'
    )
    
    # UUID5 should generate the same ID for identical inputs
    assert record1.media_item_id == record2.media_item_id


def test_coordinate_metadata_all_exif_fields(test_file_info):
    """Test that all EXIF fields are extracted."""
    metadata_ext = {
        'success': True,
        'mime_type': 'image/jpeg',
        'crc32': 'a1b2c3d4',
        'content_fingerprint': 'f' * 64,
        'width': 1920,
        'height': 1080,
        'exif_data': {
            'datetime_original': datetime(2023, 7, 1, 12, 30, 0, tzinfo=timezone.utc),
            'datetime_digitized': datetime(2023, 7, 1, 12, 35, 0, tzinfo=timezone.utc),
            'camera_make': 'Canon',
            'camera_model': 'EOS R5',
            'lens_make': 'Canon',
            'lens_model': 'RF 24-70mm F2.8',
            'focal_length': 50.0,
            'f_number': 2.8,
            'iso': 100,
            'exposure_time': '1/1000',
            'orientation': 1,
            'gps': {
                'latitude': 37.7749,
                'longitude': -122.4194,
                'altitude': 10.5
            }
        },
        'video_data': None,
        'error': None
    }
    
    record, _ = coordinate_metadata(
        file_info=test_file_info,
        metadata_ext=metadata_ext,
        album_id='album-123',
        scan_run_id='scan-456'
    )
    
    assert record.exif_datetime_original == datetime(2023, 7, 1, 12, 30, 0, tzinfo=timezone.utc)
    assert record.exif_datetime_digitized == datetime(2023, 7, 1, 12, 35, 0, tzinfo=timezone.utc)
    assert record.exif_lens_make == 'Canon'
    assert record.exif_lens_model == 'RF 24-70mm F2.8'
    assert record.exif_focal_length == 50.0
    assert record.exif_f_number == 2.8
    assert record.exif_iso == 100
    assert record.exif_exposure_time == '1/1000'
    assert record.exif_orientation == 1


def test_coordinate_metadata_with_people_tags(tmp_path, test_metadata_ext):
    """Test that people tags are extracted from JSON sidecar."""
    # Create file with JSON sidecar containing people
    file_path = tmp_path / "test.jpg"
    file_path.write_text("fake image", encoding='utf-8')
    
    json_path = tmp_path / "test.jpg.json"
    json_data = {
        "title": "Family Photo",
        "people": [
            {"name": "John Doe"},
            {"name": "Jane Smith"}
        ]
    }
    json_path.write_text(json.dumps(json_data), encoding='utf-8')
    
    file_info = FileInfo(
        file_path=file_path,
        relative_path=Path("Album/test.jpg"),
        album_folder_path=Path("Album"),
        json_sidecar_path=json_path,
        file_size=100
    )
    
    record, people_names = coordinate_metadata(
        file_info=file_info,
        metadata_ext=test_metadata_ext,
        album_id='album-123',
        scan_run_id='scan-456'
    )
    
    # People should be extracted
    assert people_names == ["John Doe", "Jane Smith"]
    assert record.title == "Family Photo"
