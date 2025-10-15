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
