"""Tests for post-scan validation."""

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from gphotos_321sync.media_scanner.post_scan import (
    validate_scan,
    cleanup_old_scan_data,
)
from gphotos_321sync.media_scanner.database import DatabaseConnection
from gphotos_321sync.media_scanner.migrations import MigrationRunner
from gphotos_321sync.media_scanner.dal.scan_runs import ScanRunDAL
from gphotos_321sync.media_scanner.dal.media_items import MediaItemDAL
from gphotos_321sync.media_scanner.dal.albums import AlbumDAL
from gphotos_321sync.media_scanner.dal.processing_errors import ProcessingErrorDAL
from tests.test_helpers import create_media_item_record


@pytest.fixture
def test_db(tmp_path):
    """Create a test database."""
    db_path = tmp_path / "test.db"
    
    # Initialize database
    db_conn = DatabaseConnection(db_path)
    
    # Get schema directory
    schema_dir = Path(__file__).parent.parent / "src" / "gphotos_321sync" / "media_scanner" / "schema"
    
    # Run migrations
    runner = MigrationRunner(db_conn, schema_dir)
    runner.apply_migrations()
    
    db_conn.close()
    
    return db_path


class TestValidateScan:
    """Tests for validate_scan function."""
    
    def test_marks_inconsistent_files(self, test_db):
        """Test that files from previous scans with old timestamps are marked inconsistent."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        scan_run_dal = ScanRunDAL(conn)
        media_dal = MediaItemDAL(conn)
        album_dal = AlbumDAL(conn)
        
        # Create OLD scan run
        old_scan_run_id = scan_run_dal.create_scan_run()
        
        # Create album
        album_id = str(uuid.uuid4())
        album_dal.insert_album({
            'album_id': album_id,
            'album_folder_path': "Photos/Test Album",
            'scan_run_id': old_scan_run_id,
        })
        
        # Create media item with OLD scan_run_id and old timestamp
        # Use UTC timezone-aware datetime
        old_timestamp = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        media_item_id = str(uuid.uuid4())
        
        conn.execute(
            """
            INSERT INTO media_items (
                media_item_id, relative_path, album_id, file_size,
                scan_run_id, status, first_seen_timestamp, last_seen_timestamp
            ) VALUES (?, ?, ?, ?, ?, 'present', ?, ?)
            """,
            (media_item_id, "Photos/Test Album/test.jpg", album_id, 1000, old_scan_run_id, old_timestamp, old_timestamp)
        )
        conn.commit()
        
        # Create NEW scan run
        scan_start_time = datetime.now(timezone.utc)
        new_scan_run_id = scan_run_dal.create_scan_run()
        
        conn.close()
        
        # Run validation
        stats = validate_scan(str(test_db), new_scan_run_id, scan_start_time)
        
        # Verify file was marked inconsistent
        assert stats['inconsistent_files'] == 1
        
        # Verify in database
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        cursor = conn.execute(
            "SELECT status FROM media_items WHERE media_item_id = ?",
            (media_item_id,)
        )
        status = cursor.fetchone()[0]
        conn.close()
        
        assert status == 'inconsistent'
    
    def test_marks_missing_files(self, test_db):
        """Test that files with old scan_run_id and status='present' are marked missing."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        scan_run_dal = ScanRunDAL(conn)
        media_dal = MediaItemDAL(conn)
        album_dal = AlbumDAL(conn)
        
        # Create old scan run
        old_scan_run_id = scan_run_dal.create_scan_run()
        
        # Create album
        album_id = str(uuid.uuid4())
        album_dal.insert_album({
            'album_id': album_id,
            'album_folder_path': "Photos/Test Album",
            'scan_run_id': old_scan_run_id,
        })
        
        # Create media item with old scan_run_id
        media_item_id = str(uuid.uuid4())
        media_dal.insert_media_item(create_media_item_record(
            media_item_id=media_item_id,
            relative_path="Photos/Test Album/old.jpg",
            album_id=album_id,
            file_size=1000,
            scan_run_id=old_scan_run_id,
        ))
        
        # Create new scan run (capture start time BEFORE creating scan)
        # Use UTC timezone-aware datetime
        scan_start_time = datetime.now(timezone.utc)
        new_scan_run_id = scan_run_dal.create_scan_run()
        
        conn.close()
        
        # Run validation
        stats = validate_scan(str(test_db), new_scan_run_id, scan_start_time)
        
        # Verify file was marked missing
        assert stats['missing_files'] == 1
        
        # Verify in database
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        cursor = conn.execute(
            "SELECT status FROM media_items WHERE media_item_id = ?",
            (media_item_id,)
        )
        status = cursor.fetchone()[0]
        conn.close()
        
        assert status == 'missing'
    
    def test_marks_missing_albums(self, test_db):
        """Test that albums with old scan_run_id are marked missing."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        scan_run_dal = ScanRunDAL(conn)
        album_dal = AlbumDAL(conn)
        
        # Create old scan run
        old_scan_run_id = scan_run_dal.create_scan_run()
        
        # Create album with old scan_run_id
        album_folder_path = "Photos/Old Album"
        album_id = album_dal.insert_album({
            'album_folder_path': album_folder_path,
            'scan_run_id': old_scan_run_id,
        })
        
        # Create new scan run (capture start time BEFORE creating scan)
        # Use UTC timezone-aware datetime
        scan_start_time = datetime.now(timezone.utc)
        new_scan_run_id = scan_run_dal.create_scan_run()
        
        conn.close()
        
        # Run validation
        stats = validate_scan(str(test_db), new_scan_run_id, scan_start_time)
        
        # Verify album was marked missing
        assert stats['missing_albums'] == 1
        
        # Verify in database
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        cursor = conn.execute(
            "SELECT status FROM albums WHERE album_id = ?",
            (album_id,)
        )
        status = cursor.fetchone()[0]
        conn.close()
        
        assert status == 'missing'
    
    def test_validation_statistics(self, test_db):
        """Test that validation returns correct statistics."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        scan_run_dal = ScanRunDAL(conn)
        media_dal = MediaItemDAL(conn)
        album_dal = AlbumDAL(conn)
        
        # Create scan run (capture start time BEFORE creating scan)
        # Use UTC timezone-aware datetime
        scan_start_time = datetime.now(timezone.utc)
        scan_run_id = scan_run_dal.create_scan_run()
        
        # Create album
        album_id = str(uuid.uuid4())
        album_dal.insert_album({
            'album_id': album_id,
            'album_folder_path': "Photos/Test Album",
            'scan_run_id': scan_run_id,
        })
        
        # Create various files
        # Present file
        media_dal.insert_media_item(create_media_item_record(
            media_item_id=str(uuid.uuid4()),
            relative_path="Photos/Test Album/present.jpg",
            album_id=album_id,
            file_size=1000,
            scan_run_id=scan_run_id,
        ))
        
        # Error file
        error_item_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO media_items (
                media_item_id, relative_path, album_id, file_size,
                scan_run_id, status
            ) VALUES (?, ?, ?, ?, ?, 'error')
            """,
            (error_item_id, "Photos/Test Album/error.jpg", album_id, 1000, scan_run_id)
        )
        conn.commit()
        conn.close()
        
        # Run validation
        stats = validate_scan(str(test_db), scan_run_id, scan_start_time)
        
        # Verify statistics
        assert stats['scan_run_id'] == scan_run_id
        assert stats['total_files'] == 2
        assert stats['present_files'] == 1
        assert stats['error_files'] == 1
        assert stats['missing_files'] == 0
        assert stats['inconsistent_files'] == 0
    
    def test_no_changes_when_all_valid(self, test_db):
        """Test that validation doesn't change anything when all files are valid."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        scan_run_dal = ScanRunDAL(conn)
        media_dal = MediaItemDAL(conn)
        album_dal = AlbumDAL(conn)
        
        # Create scan run (capture start time BEFORE creating scan)
        # Use UTC timezone-aware datetime
        scan_start_time = datetime.now(timezone.utc)
        scan_run_id = scan_run_dal.create_scan_run()
        
        # Create album
        album_id = str(uuid.uuid4())
        album_dal.insert_album({
            'album_id': album_id,
            'album_folder_path': "Photos/Test Album",
            'scan_run_id': scan_run_id,
        })
        
        # Create valid media item
        media_dal.insert_media_item(create_media_item_record(
            media_item_id=str(uuid.uuid4()),
            relative_path="Photos/Test Album/valid.jpg",
            album_id=album_id,
            file_size=1000,
            scan_run_id=scan_run_id,
        ))
        
        conn.close()
        
        # Run validation
        stats = validate_scan(str(test_db), scan_run_id, scan_start_time)
        
        # Verify no changes
        assert stats['inconsistent_files'] == 0
        assert stats['missing_files'] == 0
        assert stats['missing_albums'] == 0
        assert stats['present_files'] == 1


class TestCleanupOldScanData:
    """Tests for cleanup_old_scan_data function."""
    
    def test_keeps_recent_scans(self, test_db):
        """Test that recent scans are kept."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        scan_run_dal = ScanRunDAL(conn)
        
        # Create 5 scan runs
        scan_ids = []
        for i in range(5):
            scan_id = scan_run_dal.create_scan_run()
            scan_ids.append(scan_id)
            scan_run_dal.complete_scan_run(scan_id, 'completed')
        
        conn.close()
        
        # Clean up, keeping 3 most recent
        stats = cleanup_old_scan_data(str(test_db), keep_recent_scans=3)
        
        # Verify 2 were deleted
        assert stats['scan_runs_deleted'] == 2
        
        # Verify correct scans remain
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        cursor = conn.execute("SELECT scan_run_id FROM scan_runs ORDER BY start_timestamp DESC")
        remaining_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        assert len(remaining_ids) == 3
        # Verify the remaining scans are from the original set (order may vary due to timing)
        assert all(scan_id in scan_ids for scan_id in remaining_ids)
    
    def test_deletes_old_errors(self, test_db):
        """Test that errors from old scans are deleted."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        scan_run_dal = ScanRunDAL(conn)
        error_dal = ProcessingErrorDAL(conn)
        
        # Create 3 scan runs with errors
        scan_ids = []
        for i in range(3):
            scan_id = scan_run_dal.create_scan_run()
            scan_ids.append(scan_id)
            
            # Add error for this scan
            error_dal.insert_error(
                scan_run_id=scan_id,
                relative_path=f"Photos/error{i}.jpg",
                error_type="media_file",
                error_category="corrupted",
                error_message=f"Error {i}",
            )
            
            scan_run_dal.complete_scan_run(scan_id, 'completed')
        
        conn.close()
        
        # Clean up, keeping 1 most recent
        stats = cleanup_old_scan_data(str(test_db), keep_recent_scans=1)
        
        # Verify 2 scans and 2 errors were deleted
        assert stats['scan_runs_deleted'] == 2
        assert stats['errors_deleted'] == 2
        
        # Verify only 1 error remains
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        cursor = conn.execute("SELECT COUNT(*) FROM processing_errors")
        error_count = cursor.fetchone()[0]
        conn.close()
        
        assert error_count == 1
    
    def test_no_cleanup_when_under_limit(self, test_db):
        """Test that nothing is deleted when under the keep limit."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        scan_run_dal = ScanRunDAL(conn)
        
        # Create 3 scan runs
        for i in range(3):
            scan_id = scan_run_dal.create_scan_run()
            scan_run_dal.complete_scan_run(scan_id, 'completed')
        
        conn.close()
        
        # Clean up, keeping 10 (more than we have)
        stats = cleanup_old_scan_data(str(test_db), keep_recent_scans=10)
        
        # Verify nothing was deleted
        assert stats['scan_runs_deleted'] == 0
        assert stats['errors_deleted'] == 0
    
    def test_preserves_media_items(self, test_db):
        """Test that media items are not deleted during cleanup."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        scan_run_dal = ScanRunDAL(conn)
        media_dal = MediaItemDAL(conn)
        album_dal = AlbumDAL(conn)
        
        # Create old scan run
        old_scan_id = scan_run_dal.create_scan_run()
        
        # Create album
        album_id = str(uuid.uuid4())
        album_dal.insert_album({
            'album_id': album_id,
            'album_folder_path': "Photos/Test Album",
            'scan_run_id': old_scan_id,
        })
        
        # Create media item
        media_dal.insert_media_item(create_media_item_record(
            media_item_id=str(uuid.uuid4()),
            relative_path="Photos/Test Album/test.jpg",
            album_id=album_id,
            file_size=1000,
            scan_run_id=old_scan_id,
        ))
        
        scan_run_dal.complete_scan_run(old_scan_id, 'completed')
        
        # Create new scan run
        new_scan_id = scan_run_dal.create_scan_run()
        scan_run_dal.complete_scan_run(new_scan_id, 'completed')
        
        conn.close()
        
        # Clean up, keeping 1 (should delete old scan but not media item)
        stats = cleanup_old_scan_data(str(test_db), keep_recent_scans=1)
        
        assert stats['scan_runs_deleted'] == 1
        
        # Verify media item still exists
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        cursor = conn.execute("SELECT COUNT(*) FROM media_items")
        media_count = cursor.fetchone()[0]
        conn.close()
        
        assert media_count == 1
