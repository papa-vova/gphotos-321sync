"""Tests for archive extraction functionality."""

import pytest
import zipfile
import tarfile
import time
from pathlib import Path
from unittest.mock import Mock, patch
from gphotos_321sync.takeout_extractor.extractor import (
    ArchiveDiscovery,
    ArchiveExtractor,
    TakeoutExtractor,
    ArchiveFormat,
    ArchiveInfo,
    ExtractionState,
    ArchiveExtractionState,
)


@pytest.fixture
def temp_source_dir(tmp_path):
    """Create a temporary source directory with test archives."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    
    # Create a test ZIP file
    zip_path = source_dir / "test_archive.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr("test_file.txt", "Hello from ZIP")
        zf.writestr("subdir/nested.txt", "Nested file")
    
    # Create a test TAR.GZ file
    tar_path = source_dir / "test_archive.tar.gz"
    with tarfile.open(tar_path, 'w:gz') as tf:
        # Create in-memory file
        import io
        file_data = b"Hello from TAR.GZ"
        file_obj = io.BytesIO(file_data)
        
        tarinfo = tarfile.TarInfo(name="test_file.txt")
        tarinfo.size = len(file_data)
        tf.addfile(tarinfo, file_obj)
    
    # Create a non-archive file (should be ignored)
    (source_dir / "readme.txt").write_text("Not an archive")
    
    return source_dir


@pytest.fixture
def temp_target_media_path(tmp_path):
    """Create a temporary target media directory."""
    target_media_path = tmp_path / "target"
    target_media_path.mkdir()
    return target_media_path


class TestArchiveDiscovery:
    """Test archive discovery functionality."""
    
    def test_discover_archives(self, temp_source_dir):
        """Test discovering archives in a directory."""
        discovery = ArchiveDiscovery(temp_source_dir)
        archives = discovery.discover(recursive=False)
        
        assert len(archives) == 2
        archive_names = {a.name for a in archives}
        assert "test_archive.zip" in archive_names
        assert "test_archive.tar.gz" in archive_names
    
    def test_discover_no_archives(self, tmp_path):
        """Test discovering archives when none exist."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        discovery = ArchiveDiscovery(empty_dir)
        archives = discovery.discover()
        
        assert len(archives) == 0
    
    def test_invalid_source_dir(self, tmp_path):
        """Test error handling for invalid source directory."""
        nonexistent = tmp_path / "definitely_does_not_exist_12345"
        with pytest.raises(FileNotFoundError):
            ArchiveDiscovery(nonexistent)
    
    def test_source_is_file(self, tmp_path):
        """Test error handling when source is a file."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")
        
        with pytest.raises(NotADirectoryError):
            ArchiveDiscovery(file_path)


class TestArchiveExtractor:
    """Test archive extraction functionality."""
    
    def test_extract_zip(self, temp_source_dir, temp_target_media_path):
        """Test extracting a ZIP archive."""
        discovery = ArchiveDiscovery(temp_source_dir)
        archives = discovery.discover()
        zip_archive = next(a for a in archives if a.name.endswith('.zip'))
        
        extractor = ArchiveExtractor(temp_target_media_path, preserve_structure=False)
        result_path = extractor.extract(zip_archive)
        
        assert isinstance(result_path, Path)
        
        # Files are extracted directly to target directory (preserve_structure=False)
        extracted_file = temp_target_media_path / "test_file.txt"
        nested_file = temp_target_media_path / "subdir" / "nested.txt"
        
        assert extracted_file.exists()
        assert nested_file.exists()
        assert extracted_file.read_text() == "Hello from ZIP"
        assert nested_file.read_text() == "Nested file"
    
    def test_extract_tar_gz(self, temp_source_dir, temp_target_media_path):
        """Test extracting a TAR.GZ archive."""
        discovery = ArchiveDiscovery(temp_source_dir)
        archives = discovery.discover()
        tar_archive = next(a for a in archives if a.name.endswith('.tar.gz'))
        
        extractor = ArchiveExtractor(temp_target_media_path, preserve_structure=False)
        result_path = extractor.extract(tar_archive)
        
        assert isinstance(result_path, Path)
        
        # Files are extracted directly to target directory (preserve_structure=False)
        extracted_file = temp_target_media_path / "test_file.txt"
        
        assert extracted_file.exists()
        assert extracted_file.read_text() == "Hello from TAR.GZ"
    
    def test_extract_nonexistent_archive(self, temp_target_media_path):
        """Test extracting a nonexistent archive."""
        nonexistent_archive = ArchiveInfo(
            path=Path("/nonexistent/archive.zip"),
            format=ArchiveFormat.ZIP,
            size_bytes=0,
            name="archive.zip"
        )
        
        extractor = ArchiveExtractor(temp_target_media_path)
        
        # This should raise an exception
        with pytest.raises((ValueError, RuntimeError)):
            extractor.extract(nonexistent_archive)
    
    def test_extract_to_nonexistent_target(self, temp_source_dir):
        """Test extracting to a nonexistent target directory."""
        discovery = ArchiveDiscovery(temp_source_dir)
        archives = discovery.discover()
        archive = archives[0]
        
        nonexistent_target = Path("/nonexistent/target")
        
        # ArchiveExtractor requires target directory to exist
        with pytest.raises(FileNotFoundError, match="Target media directory does not exist"):
            ArchiveExtractor(nonexistent_target)


class TestTakeoutExtractor:
    """Test the main TakeoutExtractor class."""
    
    def test_extractor_initialization(self, temp_source_dir, temp_target_media_path):
        """Test TakeoutExtractor initialization."""
        extractor = TakeoutExtractor(
            source_dir=temp_source_dir,
            target_media_path=temp_target_media_path
        )
        
        assert extractor.discovery.source_dir == temp_source_dir
        assert extractor.extractor.target_media_path == temp_target_media_path
    
    def test_extract_all_archives(self, temp_source_dir, temp_target_media_path):
        """Test extracting all archives in source directory."""
        extractor = TakeoutExtractor(
            source_dir=temp_source_dir,
            target_media_path=temp_target_media_path
        )
        
        results = extractor.run()
        
        assert len(results) == 2
        # Verify files were extracted
        extracted_files = list(temp_target_media_path.rglob("*"))
        extracted_files = [f for f in extracted_files if f.is_file()]
        assert len(extracted_files) >= 3  # At least 3 files from both archives
    
    def test_extract_with_verification(self, temp_source_dir, temp_target_media_path):
        """Test extraction with checksum verification."""
        extractor = TakeoutExtractor(
            source_dir=temp_source_dir,
            target_media_path=temp_target_media_path,
            verify_integrity=True
        )
        
        results = extractor.run()
        
        assert len(results) == 2
    
    def test_extract_empty_source(self, tmp_path, temp_target_media_path):
        """Test extraction from empty source directory."""
        empty_source = tmp_path / "empty_source"
        empty_source.mkdir()
        
        extractor = TakeoutExtractor(
            source_dir=empty_source,
            target_media_path=temp_target_media_path
        )
        
        # Should raise RuntimeError for empty source
        with pytest.raises(RuntimeError, match="No archives found"):
            extractor.run()
    
    def test_extract_with_retry(self, temp_source_dir, temp_target_media_path):
        """Test extraction with retry mechanism."""
        extractor = TakeoutExtractor(
            source_dir=temp_source_dir,
            target_media_path=temp_target_media_path,
            max_retry_attempts=3
        )
        
        results = extractor.run()
        
        assert len(results) == 2


class TestArchiveInfo:
    """Test ArchiveInfo data structure."""
    
    def test_archive_info_creation(self):
        """Test creating ArchiveInfo objects."""
        archive_path = Path("/test/archive.zip")
        archive_info = ArchiveInfo(
            path=archive_path,
            format=ArchiveFormat.ZIP,
            size_bytes=1024,
            name="archive.zip"
        )
        
        assert archive_info.path == archive_path
        assert archive_info.format == ArchiveFormat.ZIP
        assert archive_info.size_bytes == 1024
        assert archive_info.name == "archive.zip"
    
    def test_archive_info_properties(self):
        """Test ArchiveInfo properties."""
        archive_path = Path("/test/archive.tar.gz")
        archive_info = ArchiveInfo(
            path=archive_path,
            format=ArchiveFormat.TAR_GZ,
            size_bytes=2048,
            name="archive.tar.gz"
        )
        
        assert archive_info.name == "archive.tar.gz"
        assert archive_info.format == ArchiveFormat.TAR_GZ
        assert archive_info.size_bytes == 2048


class TestArchiveFormat:
    """Test ArchiveFormat enum."""
    
    def test_archive_formats(self):
        """Test Google Takeout supported archive formats."""
        formats = [
            ArchiveFormat.ZIP,
            ArchiveFormat.TAR_GZ,
        ]
        
        assert len(formats) == 2
        assert all(isinstance(fmt, ArchiveFormat) for fmt in formats)
