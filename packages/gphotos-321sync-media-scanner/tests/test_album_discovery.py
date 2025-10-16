"""Tests for album discovery module."""

import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock

from gphotos_321sync.media_scanner.album_discovery import (
    discover_albums,
    parse_album_metadata,
    extract_year_from_folder,
    AlbumInfo
)
from gphotos_321sync.media_scanner.errors import ParseError
from gphotos_321sync.media_scanner.dal.albums import AlbumDAL


@pytest.fixture
def album_dal(tmp_path):
    """Create an AlbumDAL instance with test database."""
    from gphotos_321sync.media_scanner.database import DatabaseConnection
    from gphotos_321sync.media_scanner.migrations import MigrationRunner
    
    db_path = tmp_path / "test.db"
    db = DatabaseConnection(db_path)
    
    # Apply migrations
    schema_dir = Path(__file__).parent.parent / "src" / "gphotos_321sync" / "media_scanner" / "schema"
    runner = MigrationRunner(db, schema_dir)
    runner.apply_migrations()
    
    return AlbumDAL(db)


@pytest.fixture
def test_albums(tmp_path):
    """Create test album structure."""
    # User album with metadata.json
    user_album = tmp_path / "My Vacation"
    user_album.mkdir()
    metadata = {
        "title": "Summer Vacation 2023",
        "description": "Trip to the beach",
        "access": "private",
        "date": {"timestamp": "1688169600"}  # 2023-07-01
    }
    (user_album / "metadata.json").write_text(json.dumps(metadata))
    
    # Year-based album
    year_album = tmp_path / "Photos from 2023"
    year_album.mkdir()
    
    # Regular folder (no metadata, not year-based)
    regular = tmp_path / "Random Folder"
    regular.mkdir()
    
    # Nested album
    nested = tmp_path / "2024" / "January"
    nested.mkdir(parents=True)
    nested_metadata = {
        "title": "January Photos"
    }
    (nested / "metadata.json").write_text(json.dumps(nested_metadata))
    
    # Album with invalid metadata.json
    invalid = tmp_path / "Invalid Album"
    invalid.mkdir()
    (invalid / "metadata.json").write_text("not valid json{")
    
    return tmp_path


def test_parse_album_metadata_complete():
    """Test parsing complete album metadata."""
    tmp = Path(__file__).parent / "tmp_test_metadata.json"
    try:
        metadata = {
            "title": "Test Album",
            "description": "Test description",
            "access": "private",
            "date": {"timestamp": "1688169600"}
        }
        tmp.write_text(json.dumps(metadata))
        
        result = parse_album_metadata(tmp)
        
        assert result['title'] == "Test Album"
        assert result['description'] == "Test description"
        assert result['access_level'] == "private"
        assert isinstance(result['creation_timestamp'], datetime)
        assert result['creation_timestamp'].year == 2023
    finally:
        if tmp.exists():
            tmp.unlink()


def test_parse_album_metadata_minimal():
    """Test parsing minimal album metadata."""
    tmp = Path(__file__).parent / "tmp_test_metadata.json"
    try:
        metadata = {"title": "Minimal Album"}
        tmp.write_text(json.dumps(metadata))
        
        result = parse_album_metadata(tmp)
        
        assert result['title'] == "Minimal Album"
        assert result['description'] is None
        assert result['access_level'] is None
        assert 'creation_timestamp' not in result
    finally:
        if tmp.exists():
            tmp.unlink()


def test_parse_album_metadata_invalid_json():
    """Test parsing invalid JSON raises ParseError."""
    tmp = Path(__file__).parent / "tmp_test_metadata.json"
    try:
        tmp.write_text("not valid json{")
        
        with pytest.raises(ParseError, match="Invalid JSON"):
            parse_album_metadata(tmp)
    finally:
        if tmp.exists():
            tmp.unlink()


def test_parse_album_metadata_missing_file():
    """Test parsing non-existent file raises ParseError."""
    tmp = Path(__file__).parent / "nonexistent.json"
    
    with pytest.raises(ParseError, match="Failed to read"):
        parse_album_metadata(tmp)


def test_extract_year_from_folder_valid():
    """Test extracting year from valid folder names."""
    assert extract_year_from_folder("Photos from 2023") == 2023
    assert extract_year_from_folder("Photos from 2020") == 2020
    assert extract_year_from_folder("photos from 2019") == 2019  # Case insensitive


def test_extract_year_from_folder_invalid():
    """Test extracting year from invalid folder names."""
    assert extract_year_from_folder("My Vacation") is None
    assert extract_year_from_folder("Photos 2023") is None
    assert extract_year_from_folder("2023 Photos") is None
    assert extract_year_from_folder("Photos from 1800") is None  # Too old
    assert extract_year_from_folder("Photos from 2200") is None  # Too far future


def test_discover_albums_user_album(test_albums, album_dal):
    """Test discovering user album with metadata.json."""
    albums = list(discover_albums(test_albums, album_dal, "scan-123"))
    
    # Find the user album
    user_album = next(a for a in albums if a.title == "Summer Vacation 2023")
    
    assert user_album.is_user_album is True
    assert user_album.title == "Summer Vacation 2023"
    assert user_album.description == "Trip to the beach"
    assert user_album.access_level == "private"
    assert user_album.creation_timestamp is not None
    assert user_album.metadata_path is not None


def test_discover_albums_year_based(test_albums, album_dal):
    """Test discovering year-based album."""
    albums = list(discover_albums(test_albums, album_dal, "scan-123"))
    
    # Find the year-based album
    year_album = next(a for a in albums if "Photos from 2023" in a.title)
    
    assert year_album.is_user_album is False
    assert year_album.title == "Photos from 2023"
    assert year_album.metadata_path is None


def test_discover_albums_regular_folder(test_albums, album_dal):
    """Test discovering regular folder (no metadata, not year-based)."""
    albums = list(discover_albums(test_albums, album_dal, "scan-123"))
    
    # Find the regular folder
    regular = next(a for a in albums if a.album_folder_path == Path("Random Folder"))
    
    assert regular.is_user_album is False
    assert regular.title == "Random Folder"  # Uses folder name
    assert regular.description is None


def test_discover_albums_nested(test_albums, album_dal):
    """Test discovering nested albums."""
    albums = list(discover_albums(test_albums, album_dal, "scan-123"))
    
    # Find the nested album
    nested = next(a for a in albums if a.title == "January Photos")
    
    assert nested.album_folder_path == Path("2024") / "January"
    assert nested.is_user_album is True


def test_discover_albums_invalid_metadata(test_albums, album_dal):
    """Test handling album with invalid metadata.json."""
    albums = list(discover_albums(test_albums, album_dal, "scan-123"))
    
    # Should still discover the album, but with error status
    # Check that it was discovered (uses folder name as fallback)
    invalid = next((a for a in albums if a.album_folder_path == Path("Invalid Album")), None)
    assert invalid is not None
    assert invalid.title == "Invalid Album"  # Falls back to folder name


def test_discover_albums_database_insertion(test_albums, album_dal):
    """Test that albums are inserted into database."""
    albums = list(discover_albums(test_albums, album_dal, "scan-123"))
    
    # Check that albums were inserted
    for album in albums:
        db_album = album_dal.get_album_by_path(str(album.album_folder_path))
        assert db_album is not None
        assert db_album['album_id'] == album.album_id
        assert db_album['title'] == album.title


def test_discover_albums_album_id_generation(test_albums, album_dal):
    """Test that album IDs are deterministic (UUID5)."""
    # Discover albums twice
    albums1 = list(discover_albums(test_albums, album_dal, "scan-123"))
    albums2 = list(discover_albums(test_albums, album_dal, "scan-456"))
    
    # Same folders should have same album_ids
    albums1_dict = {str(a.album_folder_path): a.album_id for a in albums1}
    albums2_dict = {str(a.album_folder_path): a.album_id for a in albums2}
    
    for folder_path in albums1_dict:
        assert albums1_dict[folder_path] == albums2_dict[folder_path]


def test_discover_albums_empty_directory(tmp_path, album_dal):
    """Test discovering albums in empty directory."""
    albums = list(discover_albums(tmp_path, album_dal, "scan-123"))
    assert len(albums) == 0


def test_discover_albums_nonexistent_path(tmp_path, album_dal):
    """Test discovering albums with non-existent path."""
    nonexistent = tmp_path / "does_not_exist"
    albums = list(discover_albums(nonexistent, album_dal, "scan-123"))
    assert len(albums) == 0


def test_discover_albums_count(test_albums, album_dal):
    """Test that all folders are discovered as albums."""
    albums = list(discover_albums(test_albums, album_dal, "scan-123"))
    
    # Should discover all folders (including nested parent folders)
    # My Vacation, Photos from 2023, Random Folder, 2024, 2024/January, Invalid Album
    assert len(albums) >= 6


def test_discover_albums_update_existing(test_albums, album_dal):
    """Test that re-scanning updates existing albums."""
    # First scan
    albums1 = list(discover_albums(test_albums, album_dal, "scan-123"))
    
    # Second scan with different scan_run_id
    albums2 = list(discover_albums(test_albums, album_dal, "scan-456"))
    
    # Check that albums were updated (same album_id, new scan_run_id)
    for album in albums2:
        db_album = album_dal.get_album_by_path(str(album.album_folder_path))
        assert db_album['scan_run_id'] == "scan-456"
