"""Integration test to verify parallel processing works with new discovery logic."""

import tempfile
from pathlib import Path
import pytest

from gphotos_321sync.media_scanner.discovery import discover_files, FileInfo
from gphotos_321sync.media_scanner.parallel_scanner import ParallelScanner


class TestParallelProcessingCompatibility:
    """Test that parallel processing works with the new discovery logic."""
    
    def test_discovery_result_structure(self):
        """Test that discover_files returns the expected structure for parallel processing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test files with proper Google Takeout sidecar naming
            (temp_path / "photo1.jpg").touch()
            (temp_path / "photo2.png").touch()
            (temp_path / "photo1.jpg.supplemental-metadata.json").touch()
            
            # Test discover_files returns DiscoveryResult
            result = discover_files(temp_path)
            
            # Verify structure matches what parallel_scanner expects
            assert hasattr(result, 'files')
            assert hasattr(result, 'json_sidecar_count')
            assert hasattr(result, 'paired_sidecars')
            assert hasattr(result, 'all_sidecars')
            
            # Verify files are FileInfo objects
            assert len(result.files) == 1  # Only photo1.jpg has a sidecar
            assert all(isinstance(f, FileInfo) for f in result.files)
            
            # Verify FileInfo has required attributes for parallel processing
            for file_info in result.files:
                assert hasattr(file_info, 'file_path')
                assert hasattr(file_info, 'relative_path')
                assert hasattr(file_info, 'album_folder_path')
                assert hasattr(file_info, 'json_sidecar_path')
                assert hasattr(file_info, 'file_size')
                
                # These are used by worker threads
                assert isinstance(file_info.file_path, Path)
                assert isinstance(file_info.relative_path, Path)
                assert isinstance(file_info.album_folder_path, Path)
                assert file_info.json_sidecar_path is None or isinstance(file_info.json_sidecar_path, Path)
                assert isinstance(file_info.file_size, int)
    
    def test_parallel_scanner_imports_discovery(self):
        """Test that ParallelScanner can import and use discover_files."""
        # This test verifies that the import in parallel_scanner.py works
        # and that the function signature is compatible
        
        # Create a minimal scanner instance (won't actually run)
        scanner = ParallelScanner(
            db_path=Path("/tmp/test.db"),
            worker_processes=1,
            worker_threads=1
        )
        
        # Verify scanner was created successfully
        assert scanner is not None
        assert hasattr(scanner, 'scan')
    
    def test_file_info_compatibility_with_worker_threads(self):
        """Test that FileInfo objects work with worker thread processing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a test file
            test_file = temp_path / "test.jpg"
            test_file.write_bytes(b"fake image data")
            
            # Create sidecar
            sidecar_file = temp_path / "test.jpg.supplemental-metadata.json"
            sidecar_file.write_text('{"title": "Test Image"}')
            
            # Get FileInfo from discovery
            result = discover_files(temp_path)
            file_info = result.files[0]
            
            # Verify FileInfo has all attributes needed by worker threads
            # These are accessed in worker_thread.py lines 161-165
            assert file_info.file_path == test_file
            assert file_info.file_size > 0
            assert file_info.json_sidecar_path == sidecar_file
            
            # Verify relative_path is used for logging (line 282 in worker_thread.py)
            assert isinstance(file_info.relative_path, Path)
            assert file_info.relative_path.name == "test.jpg"
            
            # Verify album_folder_path is used for album mapping
            assert isinstance(file_info.album_folder_path, Path)

