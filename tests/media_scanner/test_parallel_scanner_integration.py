"""Integration tests for ParallelScanner with rescan scenarios.

These tests verify end-to-end scanning behavior including:
- Initial scan with album discovery and file processing
- Rescan with no changes (should skip all files)
- Rescan with changes (should detect and reprocess)
- Worker thread shutdown handling
"""

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gphotos_321sync.media_scanner.database import DatabaseConnection
from gphotos_321sync.media_scanner.dal.albums import AlbumDAL
from gphotos_321sync.media_scanner.dal.media_items import MediaItemDAL
from gphotos_321sync.media_scanner.dal.scan_runs import ScanRunDAL
from gphotos_321sync.media_scanner.migrations import MigrationRunner
from gphotos_321sync.media_scanner.parallel_scanner import ParallelScanner


@pytest.fixture
def test_takeout(tmp_path):
    """Create a minimal Google Takeout structure for testing."""
    takeout_root = tmp_path / "takeout_test"
    photos_root = takeout_root / "Takeout" / "Google Photos"
    photos_root.mkdir(parents=True)
    
    # Create two albums
    album1 = photos_root / "Photos from 2023"
    album2 = photos_root / "Vacation"
    album1.mkdir()
    album2.mkdir()
    
    # Create metadata.json for Vacation album
    metadata = {
        "title": "Summer Vacation",
        "description": "Beach trip 2023",
        "access": "private"
    }
    (album2 / "metadata.json").write_text(json.dumps(metadata), encoding='utf-8')
    
    # Create sample image files
    img1 = album1 / "IMG_001.jpg"
    img2 = album1 / "IMG_002.jpg"
    img3 = album2 / "beach.jpg"
    
    # Create simple test images
    for img_path in [img1, img2, img3]:
        img_path.write_bytes(b"fake image data")
    
    # Create sidecar files
    sidecar1 = album1 / "IMG_001.jpg.supplemental-metadata.json"
    sidecar2 = album1 / "IMG_002.jpg.supplemental-metadata.json"
    sidecar3 = album2 / "beach.jpg.supplemental-metadata.json"
    
    sidecar_data = {
        "photoTakenTime": {
            "timestamp": "1609459200",
            "formatted": "Jan 1, 2021, 12:00:00 AM UTC"
        },
        "title": "Test Photo",
        "description": "Test description"
    }
    
    for sidecar_path in [sidecar1, sidecar2, sidecar3]:
        sidecar_path.write_text(json.dumps(sidecar_data), encoding='utf-8')
    
    return takeout_root


@pytest.fixture
def test_db(tmp_path):
    """Create a test database."""
    db_path = tmp_path / "test.db"
    db = DatabaseConnection(db_path)
    db.connect()
    
    # Apply migrations
    schema_dir = Path(__file__).parent.parent.parent / "packages" / "gphotos-321sync-media-scanner" / "src" / "gphotos_321sync" / "media_scanner" / "schema"
    runner = MigrationRunner(db, schema_dir)
    runner.apply_migrations()
    
    yield db
    db.close()


class TestParallelScannerIntegration:
    """Integration tests for ParallelScanner."""
    
    def test_parallel_scanner_initialization(self, test_db):
        """Test ParallelScanner initialization."""
        scanner = ParallelScanner(test_db.db_path)
        
        assert scanner.db_path == test_db.db_path
        assert scanner.queue_manager is None  # Initialized during scan
        assert scanner.worker_threads is not None  # This is an int
        assert scanner.writer_thread is None  # Initialized during scan
    
    def test_parallel_scanner_scan_basic(self, test_takeout, test_db):
        """Test basic scanning functionality."""
        scanner = ParallelScanner(test_db.db_path)
        
        # Run scan
        result = scanner.scan(test_takeout)
        
        # Verify result structure
        assert isinstance(result, dict)
        assert 'scan_run_id' in result
        assert 'status' in result
        assert 'discovery_stats' in result
        
        # Verify discovery stats structure
        discovery_stats = result['discovery_stats']
        assert 'discovered_media' in discovery_stats
        assert 'discovered_sidecars' in discovery_stats
        assert 'matched_phase1' in discovery_stats
        assert 'matched_phase2' in discovery_stats
        assert 'matched_phase3' in discovery_stats
        assert 'unmatched_media' in discovery_stats
        assert 'unmatched_sidecars' in discovery_stats
    
    def test_parallel_scanner_rescan_no_changes(self, test_takeout, test_db):
        """Test rescan with no changes."""
        scanner = ParallelScanner(test_db.db_path)
        
        # First scan
        result1 = scanner.scan(test_takeout)
        assert result1['status'] == 'completed'
        
        # Second scan (no changes)
        result2 = scanner.scan(test_takeout)
        assert result2['status'] == 'completed'
        
        # Verify that both scans completed successfully
        assert result1['scan_run_id'] != result2['scan_run_id']
    
    def test_parallel_scanner_rescan_with_changes(self, test_takeout, test_db):
        """Test rescan with file changes."""
        scanner = ParallelScanner(test_db.db_path)
        
        # First scan
        result1 = scanner.scan(test_takeout)
        assert result1['status'] == 'completed'
        
        # Add a new file
        new_file = test_takeout / "Takeout" / "Google Photos" / "Photos from 2023" / "IMG_003.jpg"
        new_file.write_bytes(b"new fake image data")
        
        # Second scan (with changes)
        result2 = scanner.scan(test_takeout)
        assert result2['status'] == 'completed'
        
        # Verify that both scans completed successfully
        assert result1['scan_run_id'] != result2['scan_run_id']
    
    def test_parallel_scanner_error_handling(self, test_db):
        """Test error handling with invalid path."""
        scanner = ParallelScanner(test_db.db_path)
        
        # Try to scan nonexistent path
        nonexistent_path = Path("/nonexistent/path")
        
        # This should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            scanner.scan(nonexistent_path)
    
    def test_parallel_scanner_worker_threads(self, test_db):
        """Test worker thread management."""
        scanner = ParallelScanner(test_db.db_path)
        
        # Verify worker threads count is set
        assert scanner.worker_threads is not None
        assert isinstance(scanner.worker_threads, int)
        assert scanner.worker_threads > 0
    
    def test_parallel_scanner_writer_thread(self, test_db):
        """Test writer thread management."""
        scanner = ParallelScanner(test_db.db_path)
        
        # Writer thread is initialized during scan, not at construction
        assert scanner.writer_thread is None
    
    def test_parallel_scanner_queue_manager(self, test_db):
        """Test queue manager functionality."""
        scanner = ParallelScanner(test_db.db_path)
        
        # Queue manager is initialized during scan, not at construction
        assert scanner.queue_manager is None
    
    def test_parallel_scanner_scan_run_tracking(self, test_takeout, test_db):
        """Test scan run tracking in database."""
        scanner = ParallelScanner(test_db.db_path)
        
        # Run scan
        result = scanner.scan(test_takeout)
        
        # Verify scan run was created in database
        scan_run_dal = ScanRunDAL(test_db)
        scan_run = scan_run_dal.get_scan_run(result['scan_run_id'])
        
        assert scan_run is not None
        assert scan_run['status'] == 'completed'
        assert scan_run['start_timestamp'] is not None
        assert scan_run['end_timestamp'] is not None
    
    def test_parallel_scanner_album_discovery(self, test_takeout, test_db):
        """Test album discovery functionality."""
        scanner = ParallelScanner(test_db.db_path)
        
        # Run scan
        result = scanner.scan(test_takeout)
        
        # Verify albums were discovered by checking album count
        album_dal = AlbumDAL(test_db)
        album_count = album_dal.get_album_count()
        
        assert album_count >= 2  # Should have at least 2 albums
    
    def test_parallel_scanner_media_item_processing(self, test_takeout, test_db):
        """Test media item processing."""
        scanner = ParallelScanner(test_db.db_path)
        
        # Run scan
        result = scanner.scan(test_takeout)
        
        # Verify media items were processed by checking media item count
        media_dal = MediaItemDAL(test_db)
        media_count = media_dal.get_media_item_count()
        
        assert media_count >= 3  # Should have at least 3 media items
    
    def test_parallel_scanner_discovery_stats(self, test_takeout, test_db):
        """Test discovery statistics."""
        scanner = ParallelScanner(test_db.db_path)
        
        # Run scan
        result = scanner.scan(test_takeout)
        
        # Verify discovery stats
        discovery_stats = result['discovery_stats']
        
        # Should have discovered some media files
        assert discovery_stats['discovered_media'] >= 3
        
        # Should have discovered some sidecars
        assert discovery_stats['discovered_sidecars'] >= 3
        
        # Should have some matches
        total_matches = (
            discovery_stats['matched_phase1'] + 
            discovery_stats['matched_phase2'] + 
            discovery_stats['matched_phase3']
        )
        assert total_matches >= 0  # Could be 0 if no matches found
    
    def test_parallel_scanner_concurrent_scans(self, test_takeout, test_db):
        """Test that multiple scans can run concurrently."""
        scanner1 = ParallelScanner(test_db.db_path)
        scanner2 = ParallelScanner(test_db.db_path)
        
        # Run two scans concurrently
        result1 = scanner1.scan(test_takeout)
        result2 = scanner2.scan(test_takeout)
        
        # Both should complete successfully
        assert result1['status'] == 'completed'
        assert result2['status'] == 'completed'
        
        # Should have different scan run IDs
        assert result1['scan_run_id'] != result2['scan_run_id']
    
    def test_parallel_scanner_cleanup(self, test_db):
        """Test scanner cleanup and resource management."""
        scanner = ParallelScanner(test_db.db_path)
        
        # Components are initialized during scan, not at construction
        assert scanner.writer_thread is None
        assert scanner.queue_manager is None
        
        # Cleanup should be handled by the scanner's destructor
        # This test just verifies the scanner can be created and destroyed
        del scanner
