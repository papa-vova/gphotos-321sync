"""Tests for archive extraction functionality."""

import pytest
import zipfile
import tarfile
import time
from pathlib import Path
from unittest.mock import Mock, patch
from gphotos_321sync.processing.extractor import (
    ArchiveDiscovery,
    ArchiveExtractor,
    TakeoutExtractor,
    ArchiveFormat,
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
def temp_target_dir(tmp_path):
    """Create a temporary target directory."""
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    return target_dir


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
    
    def test_discover_recursive(self, tmp_path):
        """Test recursive archive discovery."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        # Create archive in subdirectory
        subdir = source_dir / "subdir"
        subdir.mkdir()
        
        zip_path = subdir / "nested.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("test.txt", "test")
        
        discovery = ArchiveDiscovery(source_dir)
        
        # Recursive should find it
        archives_recursive = discovery.discover(recursive=True)
        assert len(archives_recursive) == 1
        
        # Non-recursive should not
        archives_non_recursive = discovery.discover(recursive=False)
        assert len(archives_non_recursive) == 0
    
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
    
    def test_extract_zip(self, temp_source_dir, temp_target_dir):
        """Test extracting a ZIP archive."""
        discovery = ArchiveDiscovery(temp_source_dir)
        archives = discovery.discover()
        
        zip_archive = next(a for a in archives if a.format == ArchiveFormat.ZIP)
        
        extractor = ArchiveExtractor(temp_target_dir)
        extract_path = extractor.extract(zip_archive)
        
        assert extract_path.exists()
        assert (extract_path / "test_file.txt").exists()
        assert (extract_path / "subdir" / "nested.txt").exists()
    
    def test_extract_tar_gz(self, temp_source_dir, temp_target_dir):
        """Test extracting a TAR.GZ archive."""
        discovery = ArchiveDiscovery(temp_source_dir)
        archives = discovery.discover()
        
        tar_archive = next(a for a in archives if a.format == ArchiveFormat.TAR_GZ)
        
        extractor = ArchiveExtractor(temp_target_dir)
        extract_path = extractor.extract(tar_archive)
        
        assert extract_path.exists()
        assert (extract_path / "test_file.txt").exists()
    
    def test_extract_with_progress(self, temp_source_dir, temp_target_dir):
        """Test extraction with progress callback."""
        discovery = ArchiveDiscovery(temp_source_dir)
        archives = discovery.discover()
        
        zip_archive = next(a for a in archives if a.format == ArchiveFormat.ZIP)
        
        progress_calls = []
        
        def progress_callback(current, total):
            progress_calls.append((current, total))
        
        extractor = ArchiveExtractor(temp_target_dir)
        extractor.extract(zip_archive, progress_callback=progress_callback)
        
        assert len(progress_calls) > 0
        assert progress_calls[-1][0] == progress_calls[-1][1]  # Last call should be complete
    
    def test_extract_all(self, temp_source_dir, temp_target_dir):
        """Test extracting multiple archives."""
        discovery = ArchiveDiscovery(temp_source_dir)
        archives = discovery.discover()
        
        extractor = ArchiveExtractor(temp_target_dir)
        results = extractor.extract_all(archives)
        
        assert len(results) == 2
        assert all(path is not None for path in results.values())
    
    def test_preserve_structure(self, temp_source_dir, temp_target_dir):
        """Test preserve_structure option."""
        discovery = ArchiveDiscovery(temp_source_dir)
        archives = discovery.discover()
        
        zip_archive = next(a for a in archives if a.format == ArchiveFormat.ZIP)
        
        # With preserve_structure=True (default)
        extractor_preserve = ArchiveExtractor(temp_target_dir, preserve_structure=True)
        extract_path = extractor_preserve.extract(zip_archive)
        assert extract_path.name == zip_archive.path.stem
        
        # With preserve_structure=False
        target_dir_2 = temp_target_dir.parent / "target2"
        target_dir_2.mkdir()  # Must create target directory
        extractor_no_preserve = ArchiveExtractor(target_dir_2, preserve_structure=False)
        extract_path_2 = extractor_no_preserve.extract(zip_archive)
        assert extract_path_2 == target_dir_2


class TestTakeoutExtractor:
    """Test high-level TakeoutExtractor."""
    
    def test_run(self, temp_source_dir, temp_target_dir):
        """Test complete extraction workflow."""
        extractor = TakeoutExtractor(
            source_dir=temp_source_dir,
            target_dir=temp_target_dir
        )
        
        results = extractor.run()
        
        assert len(results) == 2
        assert all(path is not None for path in results.values())
    
    def test_run_with_progress(self, temp_source_dir, temp_target_dir):
        """Test extraction with progress callback."""
        progress_calls = []
        
        def progress_callback(current, total, name):
            progress_calls.append((current, total, name))
        
        extractor = TakeoutExtractor(
            source_dir=temp_source_dir,
            target_dir=temp_target_dir
        )
        
        extractor.run(progress_callback=progress_callback)
        
        assert len(progress_calls) > 0
        assert progress_calls[-1][2] == "Complete"
    
    def test_run_no_archives(self, tmp_path):
        """Test extraction when no archives are found."""
        source_dir = tmp_path / "empty_source"
        source_dir.mkdir()
        
        target_dir = tmp_path / "target"
        target_dir.mkdir()  # Must create target directory
        
        extractor = TakeoutExtractor(
            source_dir=source_dir,
            target_dir=target_dir
        )
        
        results = extractor.run()
        
        assert len(results) == 0


class TestExtractionState:
    """Test extraction state tracking."""
    
    def test_state_save_and_load(self, tmp_path):
        """Test saving and loading extraction state."""
        state_file = tmp_path / "state.json"
        
        # Create state
        state = ExtractionState(
            session_id="test_session",
            started_at="2025-01-01T00:00:00"
        )
        
        # Save state
        state.save(state_file)
        assert state_file.exists()
        
        # Load state
        loaded_state = ExtractionState.load(state_file)
        assert loaded_state is not None
        assert loaded_state.session_id == "test_session"
    
    def test_resume_extraction(self, temp_source_dir, temp_target_dir, tmp_path):
        """Test resuming an interrupted extraction."""
        state_file = tmp_path / "state.json"
        
        # First extraction - will be interrupted
        extractor1 = ArchiveExtractor(
            temp_target_dir,
            enable_resume=True,
            state_file=state_file
        )
        
        discovery = ArchiveDiscovery(temp_source_dir)
        archives = discovery.discover()
        zip_archive = next(a for a in archives if a.format == ArchiveFormat.ZIP)
        
        # Extract
        extractor1.extract(zip_archive)
        
        # Verify state was saved
        assert state_file.exists()
        
        # Second extraction - should resume
        extractor2 = ArchiveExtractor(
            temp_target_dir,
            enable_resume=True,
            state_file=state_file
        )
        
        # Should load previous state
        assert extractor2.state is not None
        assert zip_archive.name in extractor2.state.archives


class TestRetryLogic:
    """Test retry with exponential backoff."""
    
    def test_retry_on_transient_failure(self, temp_source_dir, temp_target_dir, tmp_path):
        """Test that extraction retries on transient failures."""
        state_file = tmp_path / "state.json"
        
        extractor = ArchiveExtractor(
            temp_target_dir,
            enable_resume=True,
            state_file=state_file,
            max_retry_attempts=3,
            initial_retry_delay=0.1
        )
        
        # Test retry logic with a mock operation that fails then succeeds
        call_count = [0]
        
        def flaky_operation():
            call_count[0] += 1
            if call_count[0] < 3:
                raise OSError("Simulated network error")
            return "success"
        
        result = extractor._retry_with_backoff(flaky_operation, "test operation")
        
        assert result == "success"
        assert call_count[0] == 3  # Failed twice, succeeded on third try
    
    def test_retry_gives_up_after_max_attempts(self, temp_target_dir, tmp_path):
        """Test that retry gives up after max attempts."""
        state_file = tmp_path / "state.json"
        
        extractor = ArchiveExtractor(
            temp_target_dir,
            enable_resume=True,
            state_file=state_file,
            max_retry_attempts=2,
            initial_retry_delay=0.1
        )
        
        def always_fail():
            raise OSError("Persistent error")
        
        with pytest.raises(RuntimeError, match="Extraction failed after 2 attempts"):
            extractor._retry_with_backoff(always_fail, "test operation")
