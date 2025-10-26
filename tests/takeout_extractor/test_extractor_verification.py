"""Tests for archive verification and selective re-extraction functionality."""

import pytest
import zipfile
import zlib
from pathlib import Path
from gphotos_321sync.takeout_extractor.extractor import (
    ArchiveDiscovery,
    ArchiveExtractor,
    ArchiveFormat,
)
from gphotos_321sync.common import normalize_path as normalize_unicode_path


@pytest.fixture
def test_zip_with_files(tmp_path):
    """Create a test ZIP archive with multiple files."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    
    zip_path = source_dir / "test.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add various files with known content
        zf.writestr("file1.txt", "Content of file 1")
        zf.writestr("file2.txt", "Content of file 2" * 100)  # Larger file
        zf.writestr("dir/file3.txt", "Nested file content")
        zf.writestr("dir/file4.txt", "Another nested file")
        zf.writestr("file5.txt", "Last file")
    
    return zip_path


@pytest.fixture
def temp_target_media_path(tmp_path):
    """Create a target directory for extraction."""
    target = tmp_path / "target"
    target.mkdir()
    return target


class TestArchiveExtraction:
    """Test basic archive extraction functionality."""
    
    def test_extract_zip_with_files(self, test_zip_with_files, temp_target_media_path):
        """Test extracting a ZIP archive with multiple files."""
        discovery = ArchiveDiscovery(test_zip_with_files.parent)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(temp_target_media_path, preserve_structure=False)
        result_path = extractor.extract(archive)
        
        assert isinstance(result_path, Path)
        
        # Files are extracted directly to target directory (preserve_structure=False)
        # Verify all files were extracted
        assert (temp_target_media_path / "file1.txt").exists()
        assert (temp_target_media_path / "file2.txt").exists()
        assert (temp_target_media_path / "dir" / "file3.txt").exists()
        assert (temp_target_media_path / "dir" / "file4.txt").exists()
        assert (temp_target_media_path / "file5.txt").exists()
    
    def test_extract_empty_archive(self, tmp_path):
        """Test extracting an empty archive."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create empty ZIP
        zip_path = source_dir / "empty.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            pass  # Empty archive
        
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        
        discovery = ArchiveDiscovery(source_dir)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir)
        result_path = extractor.extract(archive)
        
        assert isinstance(result_path, Path)
    
    def test_extract_unicode_filenames(self, tmp_path):
        """Test extracting archives with Unicode filenames."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        zip_path = source_dir / "unicode.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("файл.txt", "Unicode content")
            zf.writestr("文件.txt", "Chinese content")
            zf.writestr("ファイル.txt", "Japanese content")
        
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        
        discovery = ArchiveDiscovery(source_dir)
        archives = discovery.discover()
        archive = archives[0]
        
        extractor = ArchiveExtractor(target_dir, preserve_structure=False)
        result_path = extractor.extract(archive)
        
        assert isinstance(result_path, Path)
        
        # Files are extracted directly to target directory (preserve_structure=False)
        # Verify Unicode files were extracted
        assert (target_dir / "файл.txt").exists()
        assert (target_dir / "文件.txt").exists()
        assert (target_dir / "ファイル.txt").exists()
    
    def test_extract_nonexistent_target(self, test_zip_with_files):
        """Test extracting to a nonexistent target directory."""
        discovery = ArchiveDiscovery(test_zip_with_files.parent)
        archives = discovery.discover()
        archive = archives[0]
        
        nonexistent_target = Path("/nonexistent/target")
        
        # ArchiveExtractor requires target directory to exist
        with pytest.raises(FileNotFoundError, match="Target media directory does not exist"):
            ArchiveExtractor(nonexistent_target)
