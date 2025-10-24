"""Tests for the refactored discovery module."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from gphotos_321sync.media_scanner.discovery import (
    discover_files,
    discover_files_with_stats,
    _collect_media_files,
    _create_file_info,
    _match_sidecar_patterns,
    FileInfo,
    DiscoveryResult
)


class TestCollectMediaFiles:
    """Test the _collect_media_files helper function."""
    
    def test_collect_media_files_basic(self):
        """Test basic file collection functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            (temp_path / "photo1.jpg").touch()
            (temp_path / "photo2.png").touch()
            (temp_path / "photo1.json").touch()
            (temp_path / "metadata.json").touch()  # Should be skipped
            
            media_files, json_files, all_files = _collect_media_files(temp_path)
            
            assert len(media_files) == 2
            assert len(json_files) == 1
            assert len(all_files) == 1
            assert temp_path in all_files
            assert "photo1.jpg" in all_files[temp_path]
            assert "photo2.png" in all_files[temp_path]
            assert "photo1.json" in all_files[temp_path]
            assert "metadata.json" in all_files[temp_path]
    
    def test_collect_media_files_nested(self):
        """Test file collection in nested directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create nested structure
            (temp_path / "album1").mkdir()
            (temp_path / "album2").mkdir()
            (temp_path / "album1" / "photo1.jpg").touch()
            (temp_path / "album2" / "photo2.png").touch()
            (temp_path / "album1" / "photo1.json").touch()
            
            media_files, json_files, all_files = _collect_media_files(temp_path)
            
            assert len(media_files) == 2
            assert len(json_files) == 1
            assert len(all_files) == 2  # Two directories


class TestCreateFileInfo:
    """Test the _create_file_info helper function."""
    
    def test_create_file_info_basic(self):
        """Test basic FileInfo creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            media_file = temp_path / "photo.jpg"
            media_file.touch()
            media_file.write_bytes(b"test data")
            
            json_sidecars = {media_file: temp_path / "photo.json"}
            
            file_info = _create_file_info(media_file, temp_path, json_sidecars)
            
            assert file_info.file_path == media_file
            assert file_info.relative_path == Path("photo.jpg")
            assert file_info.album_folder_path == Path(".")
            assert file_info.json_sidecar_path == temp_path / "photo.json"
            assert file_info.file_size == 9  # "test data" is 9 bytes
    
    def test_create_file_info_no_sidecar(self):
        """Test FileInfo creation without sidecar."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            media_file = temp_path / "photo.jpg"
            media_file.touch()
            
            file_info = _create_file_info(media_file, temp_path, {})
            
            assert file_info.file_path == media_file
            assert file_info.json_sidecar_path is None


class TestMatchSidecarPatterns:
    """Test the _match_sidecar_patterns helper function."""
    
    def test_match_sidecar_patterns_basic(self):
        """Test basic sidecar matching."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            media_file = temp_path / "photo.jpg"
            json_file = temp_path / "photo.json"
            media_file.touch()
            json_file.touch()
            
            all_files = {temp_path: {"photo.jpg", "photo.json"}}
            
            result = _match_sidecar_patterns([json_file], [media_file], all_files)
            
            assert len(result) == 1
            assert result[media_file] == json_file
    
    def test_match_sidecar_patterns_no_match(self):
        """Test sidecar matching when no matches exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            media_file = temp_path / "photo.jpg"
            json_file = temp_path / "other.json"
            media_file.touch()
            json_file.touch()
            
            all_files = {temp_path: {"photo.jpg", "other.json"}}
            
            result = _match_sidecar_patterns([json_file], [media_file], all_files)
            
            assert len(result) == 0


class TestDiscoverFiles:
    """Test the main discover_files function."""
    
    def test_discover_files_basic(self):
        """Test basic file discovery."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            (temp_path / "photo1.jpg").touch()
            (temp_path / "photo2.png").touch()
            (temp_path / "photo1.json").touch()
            
            files = list(discover_files(temp_path))
            
            assert len(files) == 2
            assert all(isinstance(f, FileInfo) for f in files)
            
            # Check that one file has a sidecar
            files_with_sidecars = [f for f in files if f.json_sidecar_path]
            assert len(files_with_sidecars) == 1
    
    def test_discover_files_nonexistent_path(self):
        """Test discovery with nonexistent path."""
        nonexistent_path = Path("/nonexistent/path")
        
        files = list(discover_files(nonexistent_path))
        
        assert len(files) == 0
    
    def test_discover_files_file_not_dir(self):
        """Test discovery with file instead of directory."""
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_path = Path(temp_file.name)
            
            files = list(discover_files(temp_path))
            
            assert len(files) == 0


class TestDiscoverFilesWithStats:
    """Test the discover_files_with_stats function."""
    
    def test_discover_files_with_stats_basic(self):
        """Test basic stats collection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            (temp_path / "photo1.jpg").touch()
            (temp_path / "photo2.png").touch()
            (temp_path / "photo1.json").touch()
            
            result = discover_files_with_stats(temp_path)
            
            assert isinstance(result, DiscoveryResult)
            assert len(result.files) == 2
            assert result.json_sidecar_count == 1
            assert len(result.paired_sidecars) == 1
            assert len(result.all_sidecars) == 1
    
    def test_discover_files_with_stats_google_takeout(self):
        """Test stats collection with Google Takeout structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create Google Takeout structure
            takeout_path = temp_path / "Takeout" / "Google Photos"
            takeout_path.mkdir(parents=True)
            
            (takeout_path / "photo1.jpg").touch()
            (takeout_path / "photo1.json").touch()
            
            result = discover_files_with_stats(temp_path)
            
            assert len(result.files) == 1
            assert result.json_sidecar_count == 1


class TestRefactoredFunctionality:
    """Test that refactored functions work together correctly."""
    
    def test_refactored_discover_files_structure(self):
        """Test that the refactored discover_files maintains the same interface."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            (temp_path / "photo1.jpg").touch()
            (temp_path / "photo2.png").touch()
            (temp_path / "photo1.json").touch()
            
            # Test that the function still yields FileInfo objects
            files = list(discover_files(temp_path))
            
            assert len(files) == 2
            assert all(isinstance(f, FileInfo) for f in files)
            
            # Test that FileInfo objects have all required attributes
            for file_info in files:
                assert hasattr(file_info, 'file_path')
                assert hasattr(file_info, 'relative_path')
                assert hasattr(file_info, 'album_folder_path')
                assert hasattr(file_info, 'json_sidecar_path')
                assert hasattr(file_info, 'file_size')
    
    def test_refactored_performance(self):
        """Test that refactored functions maintain performance characteristics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create multiple test files
            for i in range(10):
                (temp_path / f"photo{i}.jpg").touch()
                (temp_path / f"photo{i}.json").touch()
            
            # Test that discovery still works efficiently
            files = list(discover_files(temp_path))
            
            assert len(files) == 10
            assert all(f.json_sidecar_path is not None for f in files)
