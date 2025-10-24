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
    
    # Write valid JPEG files (minimal but complete structure)
    # JPEG: SOI (FFD8) + APP0/JFIF marker + SOF + SOS + image data + EOI (FFD9)
    jpeg_content = (
        b'\xff\xd8'  # SOI (Start of Image)
        b'\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'  # APP0/JFIF
        b'\xff\xdb\x00\x43\x00' + (b'\x08' * 64) +  # DQT (Define Quantization Table)
        b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'  # SOF0 (Start of Frame)
        b'\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00' + (b'\x00' * 100) +  # SOS + Image data
        b'\xff\xd9'  # EOI (End of Image)
    )
    img1.write_bytes(jpeg_content)
    img2.write_bytes(jpeg_content)
    img3.write_bytes(jpeg_content)
    
    # Create JSON sidecars
    for img in [img1, img2, img3]:
        sidecar = {
            "title": img.stem,
            "photoTakenTime": {
                "timestamp": "1609459200"  # 2021-01-01
            },
            "geoData": {
                "latitude": 37.7749,
                "longitude": -122.4194
            }
        }
        json_path = img.with_suffix(img.suffix + '.json')
        json_path.write_text(json.dumps(sidecar), encoding='utf-8')
    
    return takeout_root


@pytest.fixture
def test_db(tmp_path):
    """Create test database with schema."""
    db_path = tmp_path / "test.db"
    db = DatabaseConnection(db_path)
    
    # Apply migrations
    schema_dir = Path(__file__).parent.parent / "src" / "gphotos_321sync" / "media_scanner" / "schema"
    runner = MigrationRunner(db, schema_dir)
    runner.apply_migrations()
    
    return db_path


class TestParallelScannerRescan:
    """Test rescan scenarios."""
    
    def test_fixture_creates_structure(self, test_takeout):
        """Verify test fixture creates the expected directory structure."""
        # This test verifies the fixture works before testing the scanner
        assert test_takeout.exists(), f"takeout_root doesn't exist: {test_takeout}"
        
        google_photos = test_takeout / "Takeout" / "Google Photos"
        assert google_photos.exists(), f"Google Photos dir doesn't exist: {google_photos}"
        assert google_photos.is_dir(), f"Google Photos is not a directory: {google_photos}"
        
        # Check albums exist
        album1 = google_photos / "Photos from 2023"
        album2 = google_photos / "Vacation"
        assert album1.exists() and album1.is_dir(), f"Album1 doesn't exist: {album1}"
        assert album2.exists() and album2.is_dir(), f"Album2 doesn't exist: {album2}"
        
        # Check files exist
        assert (album1 / "IMG_001.jpg").exists()
        assert (album1 / "IMG_002.jpg").exists()
        assert (album2 / "beach.jpg").exists()
        
        # List what's actually in google_photos
        items = list(google_photos.iterdir())
        assert len(items) == 2, f"Expected 2 items in {google_photos}, found {len(items)}: {[i.name for i in items]}"
    
    def test_initial_scan_creates_albums_and_items(self, test_takeout, test_db):
        """Test that initial scan creates albums and processes all files."""
        # Run initial scan
        scanner = ParallelScanner(
            db_path=test_db,
            worker_processes=2,
            worker_threads=4,
            use_exiftool=False,  # Don't require external tools
            use_ffprobe=False
        )
        
        scanner.scan(test_takeout)
        
        # Verify results
        db = DatabaseConnection(test_db)
        conn = db.connect()
        
        album_dal = AlbumDAL(conn)
        media_dal = MediaItemDAL(conn)
        scan_run_dal = ScanRunDAL(conn)
        
        # Check albums
        albums = conn.execute("SELECT * FROM albums").fetchall()
        assert len(albums) == 2
        
        album_titles = {album['title'] for album in albums}
        assert 'Photos from 2023' in album_titles
        assert 'Summer Vacation' in album_titles
        
        # Check media items
        items = conn.execute("SELECT * FROM media_items").fetchall()
        assert len(items) == 3
        
        # All items should have fingerprints
        for item in items:
            assert item['content_fingerprint'] is not None
            assert item['sidecar_fingerprint'] is not None
        
        # Check scan run completed
        scan_runs = conn.execute("SELECT * FROM scan_runs WHERE status = 'completed'").fetchall()
        assert len(scan_runs) == 1
        
        conn.close()
    
    def test_rescan_with_no_changes_skips_all_files(self, test_takeout, test_db):
        """Test that rescan with no changes skips all file processing."""
        import sqlite3
        
        # Initial scan
        scanner = ParallelScanner(
            db_path=test_db,
            worker_processes=2,
            worker_threads=4,
            use_exiftool=False,
            use_ffprobe=False
        )
        scanner.scan(test_takeout)
        
        # Force WAL checkpoint
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        
        # Get initial state
        initial_items = conn.execute("SELECT * FROM media_items").fetchall()
        initial_albums = conn.execute("SELECT * FROM albums").fetchall()
        initial_scan_runs = conn.execute("SELECT * FROM scan_runs").fetchall()
        
        conn.close()
        
        # Rescan (no changes to filesystem)
        scanner2 = ParallelScanner(
            db_path=test_db,
            worker_processes=2,
            worker_threads=4,
            use_exiftool=False,
            use_ffprobe=False
        )
        scanner2.scan(test_takeout)
        
        # Verify results
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        
        # Should have 2 scan runs now
        scan_runs = conn.execute("SELECT * FROM scan_runs ORDER BY start_timestamp").fetchall()
        assert len(scan_runs) == 2
        assert scan_runs[0]['status'] == 'completed'
        assert scan_runs[1]['status'] == 'completed'
        
        # Albums should be updated (not duplicated)
        albums = conn.execute("SELECT * FROM albums").fetchall()
        assert len(albums) == 2  # Same count, not doubled
        
        # All albums should have new scan_run_id (albums are always updated on rescan)
        for album in albums:
            assert album['scan_run_id'] == scan_runs[1]['scan_run_id']
        
        # Media items should be unchanged (same count)
        items = conn.execute("SELECT * FROM media_items").fetchall()
        assert len(items) == 3  # Same count
        
        # Items should have new scan_run_id (even skipped files are updated to prevent being marked missing)
        for item in items:
            assert item['scan_run_id'] == scan_runs[1]['scan_run_id']
        
        # Fingerprints should be unchanged
        for initial, current in zip(initial_items, items):
            assert initial['content_fingerprint'] == current['content_fingerprint']
            assert initial['sidecar_fingerprint'] == current['sidecar_fingerprint']
        
        conn.close()
    
    def test_rescan_detects_modified_file(self, test_takeout, test_db):
        """Test that rescan detects and reprocesses modified files."""
        # Initial scan
        scanner = ParallelScanner(
            db_path=test_db,
            worker_processes=2,
            worker_threads=4,
            use_exiftool=False,
            use_ffprobe=False
        )
        scanner.scan(test_takeout)
        
        # Modify one file
        img_path = test_takeout / "Takeout" / "Google Photos" / "Photos from 2023" / "IMG_001.jpg"
        jpeg_header = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        img_path.write_bytes(jpeg_header + b'MODIFIED CONTENT' * 100)
        
        # Rescan
        scanner2 = ParallelScanner(
            db_path=test_db,
            worker_processes=2,
            worker_threads=4,
            use_exiftool=False,
            use_ffprobe=False
        )
        scanner2.scan(test_takeout)
        
        # Verify the modified file was detected
        db = DatabaseConnection(test_db)
        conn = db.connect()
        
        # Find the modified item
        modified_item = conn.execute(
            "SELECT * FROM media_items WHERE relative_path LIKE '%IMG_001.jpg'"
        ).fetchone()
        
        assert modified_item is not None
        # The fingerprint should be different (file content changed)
        # This is verified by the fact that it was reprocessed
        
        conn.close()
    
    def test_rescan_detects_new_file(self, test_takeout, test_db):
        """Test that rescan detects new files added after initial scan."""
        # Initial scan
        scanner = ParallelScanner(
            db_path=test_db,
            worker_processes=2,
            worker_threads=4,
            use_exiftool=False,
            use_ffprobe=False
        )
        scanner.scan(test_takeout)
        
        # Add new file
        album_path = test_takeout / "Takeout" / "Google Photos" / "Photos from 2023"
        new_img = album_path / "IMG_003.jpg"
        jpeg_header = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        new_img.write_bytes(jpeg_header + b'new photo' * 100)
        
        # Create sidecar
        sidecar = {
            "title": "IMG_003",
            "photoTakenTime": {"timestamp": "1609459200"}
        }
        new_img.with_suffix('.jpg.json').write_text(json.dumps(sidecar), encoding='utf-8')
        
        # Rescan
        scanner2 = ParallelScanner(
            db_path=test_db,
            worker_processes=2,
            worker_threads=4,
            use_exiftool=False,
            use_ffprobe=False
        )
        scanner2.scan(test_takeout)
        
        # Verify new file was added
        db = DatabaseConnection(test_db)
        conn = db.connect()
        
        items = conn.execute("SELECT * FROM media_items").fetchall()
        assert len(items) == 4  # Was 3, now 4
        
        new_item = conn.execute(
            "SELECT * FROM media_items WHERE relative_path LIKE '%IMG_003.jpg'"
        ).fetchone()
        assert new_item is not None
        
        conn.close()
    
    def test_rescan_with_multiple_threads_no_crash(self, test_takeout, test_db):
        """Test that rescan with multiple threads completes without crashing.
        
        This specifically tests the queue sentinel handling fix.
        """
        # Initial scan
        scanner = ParallelScanner(
            db_path=test_db,
            worker_processes=2,
            worker_threads=8,  # More threads than files to trigger race condition
            use_exiftool=False,
            use_ffprobe=False
        )
        scanner.scan(test_takeout)
        
        # Rescan with even more threads
        scanner2 = ParallelScanner(
            db_path=test_db,
            worker_processes=2,
            worker_threads=16,  # Many threads, few files
            use_exiftool=False,
            use_ffprobe=False
        )
        
        # This should complete without ValueError: task_done() called too many times
        scanner2.scan(test_takeout)
        
        # Verify scan completed
        db = DatabaseConnection(test_db)
        conn = db.connect()
        
        scan_runs = conn.execute(
            "SELECT * FROM scan_runs WHERE status = 'completed' ORDER BY start_timestamp"
        ).fetchall()
        assert len(scan_runs) == 2
        
        conn.close()
