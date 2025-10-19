"""Tests for JSON sidecar parser."""

import pytest
import json
import tempfile
from pathlib import Path

from gphotos_321sync.media_scanner.metadata.json_parser import parse_json_sidecar


@pytest.fixture
def temp_json_file():
    """Create a temporary JSON file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        temp_path = Path(f.name)
    yield temp_path
    temp_path.unlink(missing_ok=True)


def test_parse_complete_json(temp_json_file):
    """Test parsing a complete JSON sidecar."""
    data = {
        "title": "IMG_001.jpg",
        "description": "A beautiful sunset",
        "photoTakenTime": {
            "timestamp": "1609459200",
            "formatted": "Jan 1, 2021, 12:00:00 AM UTC"
        },
        "geoData": {
            "latitude": 37.7749,
            "longitude": -122.4194,
            "altitude": 10.5,
            "latitudeSpan": 0.001,
            "longitudeSpan": 0.001
        },
        "people": [
            {"name": "Alice"},
            {"name": "Bob"}
        ]
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    
    result = parse_json_sidecar(temp_json_file)
    
    assert result['title'] == "IMG_001.jpg"
    assert result['description'] == "A beautiful sunset"
    assert result['photoTakenTime'] is not None
    assert result['geoData']['latitude'] == 37.7749
    assert result['geoData']['longitude'] == -122.4194
    assert result['people'] == ["Alice", "Bob"]


def test_parse_minimal_json(temp_json_file):
    """Test parsing JSON with minimal fields."""
    data = {
        "title": "IMG_002.jpg"
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    
    result = parse_json_sidecar(temp_json_file)
    
    assert result['title'] == "IMG_002.jpg"
    assert 'description' not in result
    assert 'photoTakenTime' not in result
    assert 'geoData' not in result
    assert 'people' not in result


def test_parse_timestamp_formats(temp_json_file):
    """Test parsing different timestamp formats."""
    data = {
        "photoTakenTime": {
            "timestamp": "1609459200"
        }
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    assert result['photoTakenTime'] is not None
    assert 'T' in result['photoTakenTime']  # ISO format


def test_parse_creation_time_fallback(temp_json_file):
    """Test that creationTime is used when photoTakenTime is missing."""
    data = {
        "creationTime": {
            "timestamp": "1609459200"
        }
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    assert result['creationTime'] is not None


def test_parse_geo_data_exif_fallback(temp_json_file):
    """Test that geoDataExif is used when geoData is missing."""
    data = {
        "geoDataExif": {
            "latitude": 40.7128,
            "longitude": -74.0060
        }
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    assert result['geoData']['latitude'] == 40.7128
    assert result['geoData']['longitude'] == -74.0060


def test_parse_people_array(temp_json_file):
    """Test parsing people array."""
    data = {
        "people": [
            {"name": "Alice"},
            {"name": "Bob"},
            {"name": "Charlie"}
        ]
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    assert len(result['people']) == 3
    assert "Alice" in result['people']
    assert "Bob" in result['people']
    assert "Charlie" in result['people']


def test_parse_invalid_json(temp_json_file):
    """Test handling of invalid JSON."""
    temp_json_file.write_text("{ invalid json }", encoding='utf-8')
    
    with pytest.raises(json.JSONDecodeError):
        parse_json_sidecar(temp_json_file)


def test_parse_missing_file():
    """Test handling of missing file."""
    with pytest.raises(FileNotFoundError):
        parse_json_sidecar(Path("/nonexistent/file.json"))


def test_parse_empty_people_array(temp_json_file):
    """Test parsing empty people array."""
    data = {
        "people": []
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    assert result['people'] == []


def test_parse_partial_geo_data(temp_json_file):
    """Test parsing partial geo data (only lat/lon)."""
    data = {
        "geoData": {
            "latitude": 51.5074,
            "longitude": -0.1278
        }
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    assert result['geoData']['latitude'] == 51.5074
    assert result['geoData']['longitude'] == -0.1278
    assert 'altitude' not in result['geoData']


def test_parse_image_views(temp_json_file):
    """Test parsing imageViews field (note: string, not int)."""
    data = {
        "title": "IMG_001.jpg",
        "imageViews": "42"
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    assert result['imageViews'] == "42"
    assert isinstance(result['imageViews'], str)


def test_parse_app_source(temp_json_file):
    """Test parsing appSource field (Android package name)."""
    data = {
        "title": "IMG-20240102-WA0001.jpg",
        "appSource": {
            "androidPackageName": "com.whatsapp"
        }
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    assert result['appSource'] == {"androidPackageName": "com.whatsapp"}
    assert result['appSource']['androidPackageName'] == "com.whatsapp"


def test_parse_from_shared_album(temp_json_file):
    """Test parsing googlePhotosOrigin.fromSharedAlbum."""
    data = {
        "title": "VID20240523214231.mp4",
        "googlePhotosOrigin": {
            "fromSharedAlbum": {}
        }
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    assert 'googlePhotosOrigin' in result
    assert 'fromSharedAlbum' in result['googlePhotosOrigin']
    assert result['googlePhotosOrigin']['fromSharedAlbum'] == {}


def test_parse_mobile_upload_without_device_folder(temp_json_file):
    """Test parsing mobileUpload without deviceFolder (can be absent)."""
    data = {
        "title": "IMG_001.jpg",
        "googlePhotosOrigin": {
            "mobileUpload": {
                "deviceType": "ANDROID_PHONE"
            }
        }
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    assert 'googlePhotosOrigin' in result
    assert result['googlePhotosOrigin']['mobileUpload']['deviceType'] == "ANDROID_PHONE"
    assert 'deviceFolder' not in result['googlePhotosOrigin']['mobileUpload']


def test_parse_timezone_aware_timestamp(temp_json_file):
    """Test that parsed timestamps are timezone-aware (UTC)."""
    data = {
        "photoTakenTime": {
            "timestamp": "1609459200"
        }
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    # Check that timestamp is ISO format with timezone
    assert result['photoTakenTime'] is not None
    assert '+00:00' in result['photoTakenTime'] or 'Z' in result['photoTakenTime']
    # Should be 2021-01-01T00:00:00+00:00
    assert result['photoTakenTime'].startswith('2021-01-01T00:00:00')


def test_parse_complete_takeout_json(temp_json_file):
    """Test parsing a complete real-world Takeout JSON file."""
    data = {
        "title": "IMG-20240102-WA0001.jpg",
        "description": "",
        "imageViews": "6",
        "creationTime": {
            "timestamp": "1704190061",
            "formatted": "Jan 2, 2024, 10:07:41 AM UTC"
        },
        "photoTakenTime": {
            "timestamp": "1704190032",
            "formatted": "Jan 2, 2024, 10:07:12 AM UTC"
        },
        "geoData": {
            "latitude": 0.0,
            "longitude": 0.0,
            "altitude": 0.0,
            "latitudeSpan": 0.0,
            "longitudeSpan": 0.0
        },
        "people": [
            {"name": "John Doe"}
        ],
        "url": "https://photos.google.com/photo/AF1QipOC0L0cFrWJpJZ2bcsN4vx5sTzpwncFfhTiAJWS",
        "googlePhotosOrigin": {
            "mobileUpload": {
                "deviceFolder": {
                    "localFolderName": "WhatsApp Images"
                },
                "deviceType": "ANDROID_PHONE"
            }
        },
        "appSource": {
            "androidPackageName": "com.whatsapp"
        }
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    # Verify all fields are parsed
    assert result['title'] == "IMG-20240102-WA0001.jpg"
    assert result['description'] == ""
    assert result['imageViews'] == "6"
    assert result['photoTakenTime'] is not None
    assert result['geoData']['latitude'] == 0.0
    assert result['people'] == ["John Doe"]
    assert result['url'] == "https://photos.google.com/photo/AF1QipOC0L0cFrWJpJZ2bcsN4vx5sTzpwncFfhTiAJWS"
    assert result['googlePhotosOrigin']['mobileUpload']['deviceType'] == "ANDROID_PHONE"
    assert result['googlePhotosOrigin']['mobileUpload']['deviceFolder']['localFolderName'] == "WhatsApp Images"
    assert result['appSource']['androidPackageName'] == "com.whatsapp"


def test_parse_integer_timestamp(temp_json_file):
    """Test parsing timestamp as raw integer (not string in dict)."""
    data = {
        "title": "IMG_001.jpg",
        "photoTakenTime": {
            "timestamp": 1609459200,  # INTEGER, not string
            "formatted": "Jan 1, 2021, 12:00:00 AM UTC"
        }
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    assert result['photoTakenTime'] is not None
    assert 'T' in result['photoTakenTime']  # ISO format
    assert result['photoTakenTime'].startswith('2021-01-01T00:00:00')


def test_parse_direct_integer_timestamp(temp_json_file):
    """Test parsing timestamp as direct integer value (edge case)."""
    data = {
        "title": "IMG_002.jpg",
        "photoTakenTime": 1609459200  # Direct integer, no dict wrapper
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    # Should handle gracefully and convert to ISO format
    assert result['photoTakenTime'] is not None
    assert 'T' in result['photoTakenTime']
    assert result['photoTakenTime'].startswith('2021-01-01T00:00:00')


def test_parse_string_timestamp(temp_json_file):
    """Test parsing timestamp as direct string (already ISO format)."""
    data = {
        "title": "IMG_003.jpg",
        "photoTakenTime": "2021-01-01T00:00:00+00:00"  # Direct ISO string
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    # Should return as-is
    assert result['photoTakenTime'] == "2021-01-01T00:00:00+00:00"


def test_parse_malformed_timestamp_dict(temp_json_file):
    """Test parsing malformed timestamp dict (missing both timestamp and formatted)."""
    data = {
        "title": "IMG_004.jpg",
        "photoTakenTime": {
            "invalid_field": "some value"
        }
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    # Should handle gracefully and return None
    assert result['photoTakenTime'] is None


def test_parse_invalid_timestamp_value(temp_json_file):
    """Test parsing invalid timestamp value (negative, out of range)."""
    data = {
        "title": "IMG_005.jpg",
        "photoTakenTime": {
            "timestamp": -1  # Invalid negative timestamp
        }
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    # Should handle gracefully and return None
    assert result['photoTakenTime'] is None


def test_parse_null_timestamp(temp_json_file):
    """Test parsing null timestamp."""
    data = {
        "title": "IMG_006.jpg",
        "photoTakenTime": None
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    # Should handle gracefully
    assert result.get('photoTakenTime') is None


def test_parse_malformed_people_array(temp_json_file):
    """Test parsing malformed people array (missing name field)."""
    data = {
        "title": "IMG_007.jpg",
        "people": [
            {"name": "Alice"},
            {"invalid_field": "Bob"},  # Missing 'name' field
            {"name": "Charlie"}
        ]
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    # Should extract valid names and skip invalid entries
    assert len(result['people']) == 2
    assert "Alice" in result['people']
    assert "Charlie" in result['people']
    assert "Bob" not in result['people']


def test_parse_malformed_geo_data(temp_json_file):
    """Test parsing malformed geo data (non-numeric values)."""
    data = {
        "title": "IMG_008.jpg",
        "geoData": {
            "latitude": "invalid",
            "longitude": -122.4194,
            "altitude": None
        }
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    # Should handle gracefully - extract what's valid, skip invalid
    assert 'geoData' in result
    # Invalid latitude should be skipped
    assert 'latitude' not in result['geoData']
    # Valid longitude should be parsed
    assert result['geoData']['longitude'] == -122.4194
    # None altitude should be skipped
    assert 'altitude' not in result['geoData']


def test_parse_mixed_timestamp_formats(temp_json_file):
    """Test parsing with mixed timestamp formats in same file."""
    data = {
        "title": "IMG_009.jpg",
        "photoTakenTime": 1609459200,  # Integer
        "creationTime": {
            "timestamp": "1609459300"  # String in dict
        }
    }
    
    temp_json_file.write_text(json.dumps(data), encoding='utf-8')
    result = parse_json_sidecar(temp_json_file)
    
    # Both should be parsed successfully
    assert result['photoTakenTime'] is not None
    assert result['creationTime'] is not None
    assert 'T' in result['photoTakenTime']
    assert 'T' in result['creationTime']
