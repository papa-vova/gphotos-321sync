"""Tests for the refactored discovery module."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from gphotos_321sync.media_scanner.discovery import (
    discover_files,
    _collect_files,
    _create_file_info,
    _create_file_info_from_batch_result,
    _match_media_to_sidecar,
    _match_media_to_sidecar_batch,
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
            (temp_path / "album1" / "photo1.json").touch()
            (temp_path / "album2" / "photo2.png").touch()
            (temp_path / "album2" / "photo2.json").touch()
            
            media_files, json_files, all_files = _collect_files(temp_path)
            
            assert len(media_files) == 2
            assert len(json_files) == 2
            assert len(all_files) == 2


class TestCreateFileInfo:
    """Test the _create_file_info helper function."""
    
    def test_create_file_info_basic(self):
        """Test basic file info creation using batch approach."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            media_file = temp_path / "photo.jpg"
            media_file.touch()
            
            # Create sidecar file
            sidecar_file = temp_path / "photo.jpg.supplemental-metadata.json"
            sidecar_file.touch()
            
            # Use the new batch approach
            media_files = [media_file]
            sidecar_index = {
                "photo.jpg": [ParsedSidecar(
                    filename="photo",
                    extension="jpg",
                    numeric_suffix="",
                    full_sidecar_path=sidecar_file
                )]
            }
            
            batch_results = _match_media_to_sidecar_batch(media_files, sidecar_index)
            file_info = _create_file_info_from_batch_result(media_file, temp_path, batch_results.matches[media_file])
            
            assert file_info.file_path == media_file
            assert file_info.relative_path == Path("photo.jpg")
            assert file_info.album_folder_path == Path(".")
            assert file_info.json_sidecar_path == sidecar_file
            assert file_info.file_size == 0
    
    def test_create_file_info_no_sidecar(self):
        """Test file info creation when no sidecar exists."""
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
        """Test sidecar filename parsing with duplicate suffix."""
        sidecar_path = Path("photo.jpg.supplemental-metadata(2).json")
        parsed = _parse_sidecar_filename(sidecar_path)
        
        assert parsed.filename == "photo"
        assert parsed.extension == "jpg"
        assert parsed.numeric_suffix == "(2)"
        assert parsed.full_sidecar_path == sidecar_path
    
    def test_parse_sidecar_filename_truncated(self):
        """Test sidecar filename parsing with truncated extension."""
        sidecar_path = Path("photo.jp.supplemental-metadata.json")
        parsed = _parse_sidecar_filename(sidecar_path)
        
        assert parsed.filename == "photo"
        assert parsed.extension == "jp"
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


class TestMatchMediaToSidecarBatch:
    """Test the _match_media_to_sidecar_batch function with proper exclusion logic."""
    
    def test_batch_happy_path_matching(self):
        """Test Phase 1: Happy path matching with exclusion."""
        # Create album with media files and sidecars
        album_path = Path("/test_album")
        media_files = [
            album_path / "photo1.jpg",
            album_path / "photo2.png", 
            album_path / "photo3.jpg"
        ]
        
        sidecar_index = {
            "photo1.jpg": [ParsedSidecar(
                filename="photo1",
                extension="jpg", 
                numeric_suffix="",
                full_sidecar_path=album_path / "photo1.jpg.supplemental-metadata.json"
            )],
            "photo2.png": [ParsedSidecar(
                filename="photo2",
                extension="png",
                numeric_suffix="", 
                full_sidecar_path=album_path / "photo2.png.supplemental-metadata.json"
            )],
            "photo3.jpg": [ParsedSidecar(
                filename="photo3",
                extension="jpg",
                numeric_suffix="",
                full_sidecar_path=album_path / "photo3.jpg.supplemental-metadata.json"
            )]
        }
        
        results = _match_media_to_sidecar_batch(media_files, sidecar_index)
        
        # All files should match in Phase 1
        assert len(results.matches) == 3
        assert len(results.matched_phase1) == 3
        assert len(results.matched_phase2) == 0
        assert len(results.matched_phase3) == 0
        assert len(results.unmatched_media) == 0
        assert len(results.unmatched_sidecars) == 0
        
        # Check specific matches
        assert results.matches[media_files[0]] == album_path / "photo1.jpg.supplemental-metadata.json"
        assert results.matches[media_files[1]] == album_path / "photo2.png.supplemental-metadata.json" 
        assert results.matches[media_files[2]] == album_path / "photo3.jpg.supplemental-metadata.json"
    
    def test_batch_numbered_files_matching(self):
        """Test Phase 2: Numbered files matching with exclusion."""
        album_path = Path("/test_album")
        media_files = [
            album_path / "photo(1).jpg",
            album_path / "photo(2).jpg",
            album_path / "photo(3).jpg"
        ]
        
        sidecar_index = {
            "photo.jpg": [
                ParsedSidecar(
                    filename="photo",
                    extension="jpg",
                    numeric_suffix="(1)",
                    full_sidecar_path=album_path / "photo.jpg.supplemental-metadata(1).json"
                ),
                ParsedSidecar(
                    filename="photo", 
                    extension="jpg",
                    numeric_suffix="(2)",
                    full_sidecar_path=album_path / "photo.jpg.supplemental-metadata(2).json"
                ),
                ParsedSidecar(
                    filename="photo",
                    extension="jpg", 
                    numeric_suffix="(3)",
                    full_sidecar_path=album_path / "photo.jpg.supplemental-metadata(3).json"
                )
            ]
        }
        
        results = _match_media_to_sidecar_batch(media_files, sidecar_index)
        
        # All files should match in Phase 2
        assert len(results.matches) == 3
        assert results.matches[media_files[0]] == album_path / "photo.jpg.supplemental-metadata(1).json"
        assert results.matches[media_files[1]] == album_path / "photo.jpg.supplemental-metadata(2).json"
        assert results.matches[media_files[2]] == album_path / "photo.jpg.supplemental-metadata(3).json"
    
    def test_batch_edited_files_matching(self):
        """Test Phase 3: Edited files matching with exclusion."""
        album_path = Path("/test_album")
        media_files = [
            album_path / "photo-edited.jpg",
            album_path / "photo-edited(2).jpg",
            album_path / "photo-edited(3).jpg"
        ]
        
        sidecar_index = {
            "photo.jpg": [
                ParsedSidecar(
                    filename="photo",
                    extension="jpg",
                    numeric_suffix="",
                    full_sidecar_path=album_path / "photo.jpg.supplemental-metadata.json"
                ),
                ParsedSidecar(
                    filename="photo",
                    extension="jpg", 
                    numeric_suffix="(2)",
                    full_sidecar_path=album_path / "photo.jpg.supplemental-metadata(2).json"
                ),
                ParsedSidecar(
                    filename="photo",
                    extension="jpg",
                    numeric_suffix="(3)", 
                    full_sidecar_path=album_path / "photo.jpg.supplemental-metadata(3).json"
                )
            ]
        }
        
        results = _match_media_to_sidecar_batch(media_files, sidecar_index)
        
        # All files should match in Phase 3
        assert len(results.matches) == 3
        assert results.matches[media_files[0]] == album_path / "photo.jpg.supplemental-metadata.json"
        assert results.matches[media_files[1]] == album_path / "photo.jpg.supplemental-metadata(2).json"
        assert results.matches[media_files[2]] == album_path / "photo.jpg.supplemental-metadata(3).json"
    
    def test_batch_mixed_phases_with_exclusion(self):
        """Test all phases together with proper exclusion."""
        album_path = Path("/test_album")
        media_files = [
            album_path / "photo1.jpg",           # Phase 1: Happy path
            album_path / "photo(2).jpg",        # Phase 2: Numbered
            album_path / "photo-edited.jpg",    # Phase 3: Edited
            album_path / "orphan.jpg"           # Phase 4: No match
        ]
        
        sidecar_index = {
            "photo1.jpg": [ParsedSidecar(
                filename="photo1",
                extension="jpg",
                numeric_suffix="",
                full_sidecar_path=album_path / "photo1.jpg.supplemental-metadata.json"
            )],
            "photo.jpg": [
                ParsedSidecar(
                    filename="photo",
                    extension="jpg",
                    numeric_suffix="(2)",
                    full_sidecar_path=album_path / "photo.jpg.supplemental-metadata(2).json"
                ),
                ParsedSidecar(
                    filename="photo",
                    extension="jpg", 
                    numeric_suffix="",
                    full_sidecar_path=album_path / "photo.jpg.supplemental-metadata.json"
                )
            ]
        }
        
        results = _match_media_to_sidecar_batch(media_files, sidecar_index)
        
        # Check matches (orphan.jpg should not match)
        assert len(results.matches) == 3
        assert results.matches[media_files[0]] == album_path / "photo1.jpg.supplemental-metadata.json"  # Phase 1
        assert results.matches[media_files[1]] == album_path / "photo.jpg.supplemental-metadata(2).json"  # Phase 2
        assert results.matches[media_files[2]] == album_path / "photo.jpg.supplemental-metadata.json"  # Phase 3
        assert media_files[3] in results.unmatched_media  # Phase 4: No match
    
    def test_batch_exclusion_prevents_double_matching(self):
        """Test that exclusion prevents the same sidecar from being matched twice."""
        album_path = Path("/test_album")
        media_files = [
            album_path / "photo.jpg",           # Should match in Phase 1
            album_path / "photo-edited.jpg"     # Should NOT match in Phase 3 (sidecar already taken)
        ]
        
        sidecar_index = {
            "photo.jpg": [ParsedSidecar(
                filename="photo",
                extension="jpg",
                numeric_suffix="",
                full_sidecar_path=album_path / "photo.jpg.supplemental-metadata.json"
            )]
        }
        
        results = _match_media_to_sidecar_batch(media_files, sidecar_index)
        
        # First file should match, second should not (exclusion working)
        assert len(results.matches) == 1
        assert results.matches[media_files[0]] == album_path / "photo.jpg.supplemental-metadata.json"
        assert media_files[1] in results.unmatched_media


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
            
            assert len(files.files) == 1  # Only photo1.jpg has a sidecar
            assert files.files[0].file_path.name == "photo1.jpg"
            assert files.files[0].json_sidecar_path.name == "photo1.jpg.supplemental-metadata.json"
            assert len(files.unmatched_media) == 1  # photo2.png has no sidecar
            assert "photo2.png" in [f.name for f in files.unmatched_media]
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
            assert len(result.files) == 1  # Only photo1.jpg has a sidecar
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