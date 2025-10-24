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
    sidecar.write_text("not valid json {")
    
    ts = parse_sidecar_timestamp(sidecar)
    
    assert ts is None


def test_parse_sidecar_timestamp_invalid_timestamp(tmp_path):
    """Test parsing sidecar with invalid timestamp value."""
    sidecar = tmp_path / "photo.jpg.supplemental-metadata.json"
    sidecar.write_text(json.dumps({
        "photoTakenTime": {
            "timestamp": "not_a_number"
        }
    }))
    
    ts = parse_sidecar_timestamp(sidecar)
    
    assert ts is None


def test_timestamps_match_exact():
    """Test exact timestamp match."""
    ts1 = datetime(2021, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2021, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    assert timestamps_match(ts1, ts2, tolerance_seconds=1)


def test_timestamps_match_within_tolerance():
    """Test timestamps match within tolerance."""
    ts1 = datetime(2021, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2021, 1, 1, 12, 0, 1, tzinfo=timezone.utc)  # 1 second later
    
    assert timestamps_match(ts1, ts2, tolerance_seconds=1)
    assert timestamps_match(ts1, ts2, tolerance_seconds=2)


def test_timestamps_match_outside_tolerance():
    """Test timestamps don't match outside tolerance."""
    ts1 = datetime(2021, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2021, 1, 1, 12, 0, 2, tzinfo=timezone.utc)  # 2 seconds later
    
    assert not timestamps_match(ts1, ts2, tolerance_seconds=1)
    assert timestamps_match(ts1, ts2, tolerance_seconds=2)


def test_timestamps_match_none():
    """Test timestamps don't match when one is None."""
    ts1 = datetime(2021, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    assert not timestamps_match(ts1, None)
    assert not timestamps_match(None, ts1)
    assert not timestamps_match(None, None)


def test_match_sidecar_by_metadata_no_exif(tmp_path):
    """Test metadata matching when media files have no EXIF data."""
    # Create sidecar with timestamp
    sidecar = tmp_path / "DSC_3767.JPG.supplemental-metadata.json"
    sidecar.write_text(json.dumps({
        "photoTakenTime": {
            "timestamp": "1609459200"
        }
    }))
    
    # Create candidate media files without EXIF
    media1 = tmp_path / "DSC_3767.JPG"
    media2 = tmp_path / "DSC_3768.JPG"
    media1.write_text("fake jpeg 1")
    media2.write_text("fake jpeg 2")
    
    # Try to match - will return None because media files have no EXIF timestamps
    match = match_sidecar_by_metadata(sidecar, [media1, media2])
    
    # Returns None because media files have no EXIF data
    assert match is None


def test_match_sidecar_by_metadata_no_sidecar_timestamp(tmp_path):
    """Test metadata matching when sidecar has no timestamp."""
    # Create sidecar without timestamp
    sidecar = tmp_path / "photo.jpg.supplemental-metadata.json"
    sidecar.write_text(json.dumps({"title": "Photo"}))
    
    # Create candidate media file
    media = tmp_path / "photo.jpg"
    media.write_text("fake jpeg")
    
    # Should return None when sidecar has no timestamp
    match = match_sidecar_by_metadata(sidecar, [media])
    
    assert match is None


def test_match_sidecar_by_metadata_empty_candidates(tmp_path):
    """Test metadata matching with no candidates."""
    # Create sidecar with timestamp
    sidecar = tmp_path / "photo.jpg.supplemental-metadata.json"
    sidecar.write_text(json.dumps({
        "photoTakenTime": {
            "timestamp": "1609459200"
        }
    }))
    
    # No candidates
    match = match_sidecar_by_metadata(sidecar, [])
    
    assert match is None
