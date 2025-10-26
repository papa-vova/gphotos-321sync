"""Tests for the refactored discovery module."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from gphotos_321sync.media_scanner.discovery import (
    discover_files,
    _collect_files,
    _create_file_info,
    _match_media_to_sidecar,
    _build_sidecar_index,
    _parse_sidecar_filename,
    FileInfo,
    ParsedSidecar,
    DiscoveryResult
)


class TestCollectFiles:
    """Test the _collect_files helper function."""
    
    def test_collect_files_basic(self):
        """Test basic file collection functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files
            (temp_path / "photo1.jpg").touch()
            (temp_path / "photo2.png").touch()
            (temp_path / "photo1.json").touch()
            (temp_path / "metadata.json").touch()  # Should be skipped
            
            media_files, json_files, all_files = _collect_files(temp_path)
            
            assert len(media_files) == 2
            assert len(json_files) == 1
            assert len(all_files) == 1
            assert temp_path in all_files
            assert "photo1.jpg" in all_files[temp_path]
            assert "photo2.png" in all_files[temp_path]
            assert "photo1.json" in all_files[temp_path]
            assert "metadata.json" in all_files[temp_path]
    
    def test_collect_files_nested(self):
        """Test file collection in nested directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create nested structure
            (temp_path / "album1").mkdir()
            (temp_path / "album2").mkdir()
            (temp_path / "album1" / "photo1.jpg").touch()
            (temp_path / "album2" / "photo2.png").touch()
            (temp_path / "album1" / "photo1.json").touch()
            
            media_files, json_files, all_files = _collect_files(temp_path)
            
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
            
            # Create sidecar index with matching sidecar (using new album-based key format)
            sidecar_index = {f"{temp_path.name}/photo.jpg": [ParsedSidecar(
                filename="photo",
                extension="jpg", 
                numeric_suffix="",
                full_sidecar_path=temp_path / "photo.json"
            )]}
            
            file_info = _create_file_info(media_file, temp_path, sidecar_index)
            
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


class TestParseSidecarFilename:
    """Test the _parse_sidecar_filename helper function."""
    
    def test_parse_sidecar_filename_basic(self):
        """Test basic sidecar filename parsing."""
        sidecar_path = Path("photo.jpg.supplemental-metadata.json")
        parsed = _parse_sidecar_filename(sidecar_path)
        
        assert parsed.filename == "photo"
        assert parsed.extension == "jpg"
        assert parsed.numeric_suffix == ""
        assert parsed.full_sidecar_path == sidecar_path
    
    def test_parse_sidecar_filename_with_duplicate(self):
        """Test parsing sidecar with duplicate suffix."""
        sidecar_path = Path("photo.jpg.supplemental-metadata(1).json")
        parsed = _parse_sidecar_filename(sidecar_path)
        
        assert parsed.filename == "photo"
        assert parsed.extension == "jpg"
        assert parsed.numeric_suffix == "(1)"
        assert parsed.full_sidecar_path == sidecar_path
    
    def test_parse_sidecar_filename_truncated(self):
        """Test parsing truncated sidecar filename."""
        sidecar_path = Path("photo.jpg.suppl.json")
        parsed = _parse_sidecar_filename(sidecar_path)
        
        assert parsed.filename == "photo"
        assert parsed.extension == "jpg"
        assert parsed.numeric_suffix == ""
        assert parsed.full_sidecar_path == sidecar_path


class TestBuildSidecarIndex:
    """Test the _build_sidecar_index helper function."""
    
    def test_build_sidecar_index_basic(self):
        """Test basic sidecar index building."""
        sidecar_filenames = [
            "photo1.jpg.supplemental-metadata.json",
            "photo2.png.supplemental-metadata.json"
        ]
        
        index = _build_sidecar_index(sidecar_filenames)
        
        assert len(index) == 2
        assert "/photo1.jpg" in index
        assert "/photo2.png" in index
        assert len(index["/photo1.jpg"]) == 1
        assert len(index["/photo2.png"]) == 1


class TestMatchMediaToSidecar:
    """Test the _match_media_to_sidecar helper function."""
    
    def test_match_media_to_sidecar_basic(self):
        """Test basic media to sidecar matching."""
        media_file = Path("/photo.jpg")  # Full path with parent directory
        sidecar_index = {
            "/photo.jpg": [ParsedSidecar(
                filename="photo",
                extension="jpg",
                numeric_suffix="",
                full_sidecar_path=Path("photo.jpg.supplemental-metadata.json")
            )]
        }
        
        result = _match_media_to_sidecar(media_file, sidecar_index)
        
        assert result == Path("photo.jpg.supplemental-metadata.json")
    
    def test_match_media_to_sidecar_no_match(self):
        """Test media to sidecar matching when no match exists."""
        media_file = Path("photo.jpg")
        sidecar_index = {}
        
        result = _match_media_to_sidecar(media_file, sidecar_index)
        
        assert result is None
    
    def test_match_media_to_sidecar_numeric_suffix_match(self):
        """Test media to sidecar matching with numeric suffix."""
        media_file = Path("/photo(2).jpg")  # Media has numeric suffix
        sidecar_index = {
            "/photo.jpg": [ParsedSidecar(
                filename="photo",
                extension="jpg",
                numeric_suffix="(2)",  # Sidecar has matching numeric suffix
                full_sidecar_path=Path("photo.jpg.supplemental-metadata(2).json")
            )]
        }
        
        result = _match_media_to_sidecar(media_file, sidecar_index)
        
        assert result == Path("photo.jpg.supplemental-metadata(2).json")
    
    def test_match_media_to_sidecar_numeric_suffix_mismatch(self):
        """Test media to sidecar matching with mismatched numeric suffix."""
        media_file = Path("/photo(2).jpg")  # Media has (2)
        sidecar_index = {
            "/photo.jpg": [ParsedSidecar(
                filename="photo",
                extension="jpg",
                numeric_suffix="(1)",  # Sidecar has (1) - mismatch
                full_sidecar_path=Path("photo.jpg.supplemental-metadata(1).json")
            )]
        }
        
        result = _match_media_to_sidecar(media_file, sidecar_index)
        
        assert result is None  # Should not match due to suffix mismatch
    
    def test_match_media_to_sidecar_multiple_candidates_no_clear_winner(self):
        """Test media to sidecar matching with multiple candidates and no clear winner."""
        media_file = Path("/photo.jpg")
        sidecar_index = {
            "/photo.jpg": [
                ParsedSidecar(
                    filename="photo",
                    extension="jpg",
                    numeric_suffix="(1)",
                    full_sidecar_path=Path("photo.jpg.supplemental-metadata(1).json")
                ),
                ParsedSidecar(
                    filename="photo",
                    extension="jpg",
                    numeric_suffix="(2)",
                    full_sidecar_path=Path("photo.jpg.supplemental-metadata(2).json")
                )
            ]
        }
        
        result = _match_media_to_sidecar(media_file, sidecar_index)
        
        assert result is None  # Should not match due to multiple candidates
    
    def test_match_media_to_sidecar_multiple_candidates_single_no_suffix(self):
        """Test media to sidecar matching with multiple candidates but only one without suffix."""
        media_file = Path("/photo.jpg")
        sidecar_index = {
            "/photo.jpg": [
                ParsedSidecar(
                    filename="photo",
                    extension="jpg",
                    numeric_suffix="",  # No suffix - this should win
                    full_sidecar_path=Path("photo.jpg.supplemental-metadata.json")
                ),
                ParsedSidecar(
                    filename="photo",
                    extension="jpg",
                    numeric_suffix="(1)",
                    full_sidecar_path=Path("photo.jpg.supplemental-metadata(1).json")
                )
            ]
        }
        
        result = _match_media_to_sidecar(media_file, sidecar_index)
        
        assert result == Path("photo.jpg.supplemental-metadata.json")
    
    def test_match_media_to_sidecar_edited_pattern(self):
        """Test media to sidecar matching with edited file pattern."""
        media_file = Path("/photo-edited.jpg")  # Media has -edited suffix
        sidecar_index = {
            "/photo.jpg": [ParsedSidecar(
                filename="photo",
                extension="jpg",
                numeric_suffix="",
                full_sidecar_path=Path("photo.jpg.supplemental-metadata.json")
            )]
        }
        
        result = _match_media_to_sidecar(media_file, sidecar_index)
        
        assert result == Path("photo.jpg.supplemental-metadata.json")
    
    def test_match_media_to_sidecar_edited_with_numeric_suffix(self):
        """Test media to sidecar matching with edited file pattern and numeric suffix."""
        media_file = Path("/photo-edited(2).jpg")  # Media has -edited and (2)
        sidecar_index = {
            "/photo.jpg": [ParsedSidecar(
                filename="photo",
                extension="jpg",
                numeric_suffix="(2)",  # Matching numeric suffix
                full_sidecar_path=Path("photo.jpg.supplemental-metadata(2).json")
            )]
        }
        
        result = _match_media_to_sidecar(media_file, sidecar_index)
        
        assert result == Path("photo.jpg.supplemental-metadata(2).json")
    
    def test_match_media_to_sidecar_album_scoped_matching(self):
        """Test that matching is scoped to the same album."""
        # Create a proper Path object with parent directory
        album1_path = Path("/Album1")
        media_file = album1_path / "photo.jpg"
        
        sidecar_index = {
            "Album1/photo.jpg": [ParsedSidecar(
                filename="photo",
                extension="jpg",
                numeric_suffix="",
                full_sidecar_path=Path("Album1/photo.jpg.supplemental-metadata.json")
            )],
            "Album2/photo.jpg": [ParsedSidecar(
                filename="photo",
                extension="jpg",
                numeric_suffix="",
                full_sidecar_path=Path("Album2/photo.jpg.supplemental-metadata.json")
            )]
        }
        
        result = _match_media_to_sidecar(media_file, sidecar_index)
        
        # Should only match the sidecar from Album1, not Album2
        assert result == Path("Album1/photo.jpg.supplemental-metadata.json")


class TestDiscoverFiles:
    """Test the main discover_files function."""
    
    def test_discover_files_basic(self):
        """Test basic file discovery."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files with proper Google Takeout sidecar naming
            (temp_path / "photo1.jpg").touch()
            (temp_path / "photo2.png").touch()
            (temp_path / "photo1.jpg.supplemental-metadata.json").touch()
            
            files = discover_files(temp_path)
            
            assert len(files.files) == 2
            assert all(isinstance(f, FileInfo) for f in files.files)
            
            # Check that one file has a sidecar
            files_with_sidecars = [f for f in files.files if f.json_sidecar_path]
            assert len(files_with_sidecars) == 1
    
    def test_discover_files_nonexistent_path(self):
        """Test discovery with nonexistent path."""
        nonexistent_path = Path("/nonexistent/path")
        
        files = discover_files(nonexistent_path)
        
        assert len(files.files) == 0
    
    def test_discover_files_file_not_dir(self):
        """Test discovery with file instead of directory."""
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_path = Path(temp_file.name)
            
            files = discover_files(temp_path)
            
            assert len(files.files) == 0


class TestRefactoredFunctionality:
    """Test that refactored functions work together correctly."""
    
    def test_refactored_discover_files_structure(self):
        """Test that the refactored discover_files maintains the same interface."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files with proper Google Takeout sidecar naming
            (temp_path / "photo1.jpg").touch()
            (temp_path / "photo2.png").touch()
            (temp_path / "photo1.jpg.supplemental-metadata.json").touch()
            
            # Test that the function returns DiscoveryResult
            result = discover_files(temp_path)
            
            assert isinstance(result, DiscoveryResult)
            assert len(result.files) == 2
            assert all(isinstance(f, FileInfo) for f in result.files)
            
            # Test that FileInfo objects have all required attributes
            for file_info in result.files:
                assert hasattr(file_info, 'file_path')
                assert hasattr(file_info, 'relative_path')
                assert hasattr(file_info, 'album_folder_path')
                assert hasattr(file_info, 'json_sidecar_path')
                assert hasattr(file_info, 'file_size')
    
    def test_refactored_performance(self):
        """Test that refactored functions maintain performance characteristics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create multiple test files with proper Google Takeout sidecar naming
            for i in range(10):
                (temp_path / f"photo{i}.jpg").touch()
                (temp_path / f"photo{i}.jpg.supplemental-metadata.json").touch()
            
            # Test that discovery still works efficiently
            result = discover_files(temp_path)
            
            assert len(result.files) == 10
            assert all(f.json_sidecar_path is not None for f in result.files)
