"""Tests for metadata-based sidecar matching.

This module tests the metadata-based fallback matching functionality which:
- Extracts timestamps from JSON sidecars (photoTakenTime)
- Extracts timestamps from media files (EXIF DateTimeOriginal or video creation_time)
- Matches sidecars to media files by comparing timestamps within tolerance
- Used as fallback when filename-based matching fails (e.g., duplicate numbered files)
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gphotos_321sync.media_scanner.metadata_matcher import (
    match_sidecar_by_metadata,
    parse_sidecar_timestamp,
    timestamps_match,
)


def test_parse_sidecar_timestamp_valid(tmp_path):
    """Test parsing valid Google Takeout sidecar timestamp."""
    sidecar = tmp_path / "photo.jpg.supplemental-metadata.json"
    sidecar.write_text(json.dumps({
        "photoTakenTime": {
            "timestamp": "1609459200",  # 2021-01-01 00:00:00 UTC
            "formatted": "Jan 1, 2021, 12:00:00 AM UTC"
        }
    }))
    
    ts = parse_sidecar_timestamp(sidecar)
    
    assert ts is not None
    assert ts == datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_parse_sidecar_timestamp_missing_field(tmp_path):
    """Test parsing sidecar without photoTakenTime field."""
    sidecar = tmp_path / "photo.jpg.supplemental-metadata.json"
    sidecar.write_text(json.dumps({
        "title": "Photo",
        "description": "Test photo"
    }))
    
    ts = parse_sidecar_timestamp(sidecar)
    
    assert ts is None


def test_parse_sidecar_timestamp_invalid_json(tmp_path):
    """Test parsing sidecar with invalid JSON."""
    sidecar = tmp_path / "photo.jpg.supplemental-metadata.json"
    sidecar.write_text("invalid json content")
    
    ts = parse_sidecar_timestamp(sidecar)
    
    assert ts is None


def test_parse_sidecar_timestamp_nonexistent_file():
    """Test parsing timestamp from nonexistent file."""
    sidecar = Path("/nonexistent/file.json")
    
    ts = parse_sidecar_timestamp(sidecar)
    
    assert ts is None


def test_parse_sidecar_timestamp_malformed_timestamp(tmp_path):
    """Test parsing sidecar with malformed timestamp."""
    sidecar = tmp_path / "photo.jpg.supplemental-metadata.json"
    sidecar.write_text(json.dumps({
        "photoTakenTime": {
            "timestamp": "invalid_timestamp",
            "formatted": "Jan 1, 2021, 12:00:00 AM UTC"
        }
    }))
    
    ts = parse_sidecar_timestamp(sidecar)
    
    assert ts is None


def test_timestamps_match_exact():
    """Test timestamp matching with exact timestamps."""
    ts1 = datetime(2021, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2021, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    assert timestamps_match(ts1, ts2, tolerance_seconds=2)


def test_timestamps_match_within_tolerance():
    """Test timestamp matching within tolerance."""
    ts1 = datetime(2021, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2021, 1, 1, 12, 0, 1, tzinfo=timezone.utc)  # 1 second difference
    
    assert timestamps_match(ts1, ts2, tolerance_seconds=2)


def test_timestamps_match_outside_tolerance():
    """Test timestamp matching outside tolerance."""
    ts1 = datetime(2021, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2021, 1, 1, 12, 0, 5, tzinfo=timezone.utc)  # 5 seconds difference
    
    assert not timestamps_match(ts1, ts2, tolerance_seconds=2)


def test_timestamps_match_none_values():
    """Test timestamp matching with None values."""
    ts1 = datetime(2021, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    assert not timestamps_match(ts1, None, tolerance_seconds=2)
    assert not timestamps_match(None, ts1, tolerance_seconds=2)
    assert not timestamps_match(None, None, tolerance_seconds=2)


def test_timestamps_match_different_timezones():
    """Test timestamp matching with different timezones."""
    ts1 = datetime(2021, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2021, 1, 1, 12, 0, 0, tzinfo=timezone.utc)  # Same UTC time
    
    assert timestamps_match(ts1, ts2, tolerance_seconds=2)


def test_match_sidecar_by_metadata_success(tmp_path):
    """Test successful metadata-based sidecar matching."""
    # Create sidecar with timestamp
    sidecar = tmp_path / "photo.jpg.supplemental-metadata.json"
    sidecar.write_text(json.dumps({
        "photoTakenTime": {
            "timestamp": "1609459200",  # 2021-01-01 00:00:00 UTC
            "formatted": "Jan 1, 2021, 12:00:00 AM UTC"
        }
    }))
    
    # Create media file (mock)
    media_file = tmp_path / "photo.jpg"
    media_file.touch()
    
    # Mock parse_media_timestamp function
    from unittest.mock import patch
    with patch('gphotos_321sync.media_scanner.metadata_matcher.parse_media_timestamp') as mock_parse:
        mock_parse.return_value = datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        
        # Test matching
        result = match_sidecar_by_metadata(sidecar, [media_file])
        
        assert result == media_file


def test_match_sidecar_by_metadata_no_match(tmp_path):
    """Test metadata-based matching when no match is found."""
    # Create sidecar with timestamp
    sidecar = tmp_path / "photo.jpg.supplemental-metadata.json"
    sidecar.write_text(json.dumps({
        "photoTakenTime": {
            "timestamp": "1609459200",  # 2021-01-01 00:00:00 UTC
            "formatted": "Jan 1, 2021, 12:00:00 AM UTC"
        }
    }))
    
    # Create media file with different timestamp
    media_file = tmp_path / "photo.jpg"
    media_file.touch()
    
    # Mock parse_media_timestamp function with different timestamp
    from unittest.mock import patch
    with patch('gphotos_321sync.media_scanner.metadata_matcher.parse_media_timestamp') as mock_parse:
        mock_parse.return_value = datetime(2021, 1, 1, 0, 0, 10, tzinfo=timezone.utc)  # 10 seconds later
        
        # Test matching
        result = match_sidecar_by_metadata(sidecar, [media_file])
        
        assert result is None


def test_match_sidecar_by_metadata_multiple_candidates(tmp_path):
    """Test metadata-based matching with multiple media file candidates."""
    # Create sidecar with timestamp
    sidecar = tmp_path / "photo.jpg.supplemental-metadata.json"
    sidecar.write_text(json.dumps({
        "photoTakenTime": {
            "timestamp": "1609459200",  # 2021-01-01 00:00:00 UTC
            "formatted": "Jan 1, 2021, 12:00:00 AM UTC"
        }
    }))
    
    # Create multiple media files
    media_file1 = tmp_path / "photo1.jpg"
    media_file2 = tmp_path / "photo2.jpg"
    media_file3 = tmp_path / "photo3.jpg"
    
    for f in [media_file1, media_file2, media_file3]:
        f.touch()
    
    # Mock parse_media_timestamp function - only one matches
    from unittest.mock import patch
    def mock_parse_side_effect(file_path, **kwargs):
        if file_path == media_file2:
            return datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc)  # Exact match
        elif file_path == media_file1:
            return datetime(2021, 1, 1, 0, 0, 1, tzinfo=timezone.utc)  # Within tolerance
        else:
            return datetime(2021, 1, 1, 0, 0, 10, tzinfo=timezone.utc)  # Outside tolerance
    
    with patch('gphotos_321sync.media_scanner.metadata_matcher.parse_media_timestamp', side_effect=mock_parse_side_effect):
        # Test matching
        result = match_sidecar_by_metadata(sidecar, [media_file1, media_file2, media_file3])
        
        # Should return the first match within tolerance
        assert result == media_file1


def test_match_sidecar_by_metadata_no_sidecar_timestamp(tmp_path):
    """Test metadata-based matching when sidecar has no timestamp."""
    # Create sidecar without timestamp
    sidecar = tmp_path / "photo.jpg.supplemental-metadata.json"
    sidecar.write_text(json.dumps({
        "title": "Photo",
        "description": "Test photo"
    }))
    
    # Create media file
    media_file = tmp_path / "photo.jpg"
    media_file.touch()
    
    # Mock parse_media_timestamp function
    from unittest.mock import patch
    with patch('gphotos_321sync.media_scanner.metadata_matcher.parse_media_timestamp') as mock_parse:
        mock_parse.return_value = datetime(2021, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        
        # Test matching
        result = match_sidecar_by_metadata(sidecar, [media_file])
        
        assert result is None


def test_match_sidecar_by_metadata_empty_candidates(tmp_path):
    """Test metadata-based matching with empty media file candidates."""
    # Create sidecar with timestamp
    sidecar = tmp_path / "photo.jpg.supplemental-metadata.json"
    sidecar.write_text(json.dumps({
        "photoTakenTime": {
            "timestamp": "1609459200",
            "formatted": "Jan 1, 2021, 12:00:00 AM UTC"
        }
    }))
    
    # Test matching with empty candidates
    result = match_sidecar_by_metadata(sidecar, [], lambda x: None)
    
    assert result is None


def test_match_sidecar_by_metadata_tolerance_edge_case(tmp_path):
    """Test metadata-based matching at tolerance boundary."""
    # Create sidecar with timestamp
    sidecar = tmp_path / "photo.jpg.supplemental-metadata.json"
    sidecar.write_text(json.dumps({
        "photoTakenTime": {
            "timestamp": "1609459200",  # 2021-01-01 00:00:00 UTC
            "formatted": "Jan 1, 2021, 12:00:00 AM UTC"
        }
    }))
    
    # Create media file with timestamp at tolerance boundary
    media_file = tmp_path / "photo.jpg"
    media_file.touch()
    
    # Mock parse_media_timestamp function - exactly at tolerance boundary
    from unittest.mock import patch
    with patch('gphotos_321sync.media_scanner.metadata_matcher.parse_media_timestamp') as mock_parse:
        mock_parse.return_value = datetime(2021, 1, 1, 0, 0, 2, tzinfo=timezone.utc)  # Exactly 2 seconds later
        
        # Test matching with 2-second tolerance
        result = match_sidecar_by_metadata(sidecar, [media_file], tolerance_seconds=2)
        
        assert result == media_file
