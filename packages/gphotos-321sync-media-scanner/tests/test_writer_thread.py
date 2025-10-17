"""Tests for writer thread."""

import threading
import time
import uuid
from pathlib import Path
from queue import Queue
import pytest

from gphotos_321sync.media_scanner.parallel.writer_thread import (
    writer_thread_main,
    _write_batch,
)
from gphotos_321sync.media_scanner.database import DatabaseConnection
from gphotos_321sync.media_scanner.migrations import MigrationRunner
from gphotos_321sync.media_scanner.dal.scan_runs import ScanRunDAL


@pytest.fixture
def test_db(tmp_path):
    """Create a test database."""
    from pathlib import Path
    
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


@pytest.fixture
def scan_run_id(test_db):
    """Create a scan run for testing."""
    db_conn = DatabaseConnection(test_db)
    conn = db_conn.connect()
    
    scan_run_dal = ScanRunDAL(conn)
    scan_run_id = scan_run_dal.create_scan_run()
    
    conn.close()
    
    return scan_run_id


@pytest.fixture
def results_queue():
    """Create a results queue."""
    return Queue()


@pytest.fixture
def shutdown_event():
    """Create a shutdown event."""
    return threading.Event()


class TestWriterThread:
    """Tests for writer thread."""
    
    def test_writes_media_items(self, test_db, scan_run_id, results_queue, shutdown_event):
        """Test writer thread writes media items to database."""
        # Add media item results to queue
        for i in range(3):
            results_queue.put({
                "type": "media_item",
                "record": {
                    "media_item_id": str(uuid.uuid4()),
                    "relative_path": f"Photos/test{i}.jpg",
                    "album_id": "album-123",
                    "file_size": 1000 + i,
                    "mime_type": "image/jpeg",
                    "scan_run_id": scan_run_id,
                    "status": "present",
                }
            })
        
        # Add sentinel
        results_queue.put(None)
        
        # Run writer thread
        thread = threading.Thread(
            target=writer_thread_main,
            args=(results_queue, str(test_db), scan_run_id, 100, shutdown_event),
        )
        thread.start()
        thread.join(timeout=2.0)
        
        assert not thread.is_alive()
        
        # Verify items were written
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        cursor = conn.execute("SELECT COUNT(*) FROM media_items")
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 3
    
    def test_writes_errors(self, test_db, scan_run_id, results_queue, shutdown_event):
        """Test writer thread writes errors to database."""
        # Add error results to queue
        for i in range(2):
            results_queue.put({
                "type": "error",
                "scan_run_id": scan_run_id,
                "relative_path": f"Photos/bad{i}.jpg",
                "error_type": "media_file",
                "error_category": "corrupted",
                "error_message": f"File {i} is corrupted",
            })
        
        results_queue.put(None)
        
        # Run writer thread
        thread = threading.Thread(
            target=writer_thread_main,
            args=(results_queue, str(test_db), scan_run_id, 100, shutdown_event),
        )
        thread.start()
        thread.join(timeout=2.0)
        
        assert not thread.is_alive()
        
        # Verify errors were written
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        cursor = conn.execute("SELECT COUNT(*) FROM processing_errors")
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 2
    
    def test_batch_writing(self, test_db, scan_run_id, results_queue, shutdown_event):
        """Test batch writing with small batch size."""
        # Add 10 items with batch size of 3
        for i in range(10):
            results_queue.put({
                "type": "media_item",
                "record": {
                    "media_item_id": str(uuid.uuid4()),
                    "relative_path": f"Photos/test{i}.jpg",
                    "album_id": "album-123",
                    "file_size": 1000 + i,
                    "mime_type": "image/jpeg",
                    "scan_run_id": scan_run_id,
                    "status": "present",
                }
            })
        
        results_queue.put(None)
        
        # Run writer thread with small batch size
        thread = threading.Thread(
            target=writer_thread_main,
            args=(results_queue, str(test_db), scan_run_id, 3, shutdown_event),
        )
        thread.start()
        thread.join(timeout=2.0)
        
        assert not thread.is_alive()
        
        # Verify all items were written
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        cursor = conn.execute("SELECT COUNT(*) FROM media_items")
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 10
    
    def test_mixed_results(self, test_db, scan_run_id, results_queue, shutdown_event):
        """Test writing mixed media items and errors."""
        # Add mix of items and errors
        results_queue.put({
            "type": "media_item",
            "record": {
                "media_item_id": str(uuid.uuid4()),
                "relative_path": "Photos/good1.jpg",
                "album_id": "album-123",
                "file_size": 1000,
                "mime_type": "image/jpeg",
                "scan_run_id": scan_run_id,
                "status": "present",
            }
        })
        
        results_queue.put({
            "type": "error",
            "scan_run_id": scan_run_id,
            "relative_path": "Photos/bad1.jpg",
            "error_type": "media_file",
            "error_category": "corrupted",
            "error_message": "Corrupted file",
        })
        
        results_queue.put({
            "type": "media_item",
            "record": {
                "media_item_id": str(uuid.uuid4()),
                "relative_path": "Photos/good2.jpg",
                "album_id": "album-123",
                "file_size": 2000,
                "mime_type": "image/jpeg",
                "scan_run_id": scan_run_id,
                "status": "present",
            }
        })
        
        results_queue.put(None)
        
        # Run writer thread
        thread = threading.Thread(
            target=writer_thread_main,
            args=(results_queue, str(test_db), scan_run_id, 100, shutdown_event),
        )
        thread.start()
        thread.join(timeout=2.0)
        
        assert not thread.is_alive()
        
        # Verify counts
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        cursor = conn.execute("SELECT COUNT(*) FROM media_items")
        media_count = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT COUNT(*) FROM processing_errors")
        error_count = cursor.fetchone()[0]
        
        conn.close()
        
        assert media_count == 2
        assert error_count == 1
    
    def test_shutdown_event(self, test_db, scan_run_id, results_queue, shutdown_event):
        """Test writer thread respects shutdown event."""
        # Set shutdown event immediately
        shutdown_event.set()
        
        # Run writer thread
        thread = threading.Thread(
            target=writer_thread_main,
            args=(results_queue, str(test_db), scan_run_id, 100, shutdown_event),
        )
        thread.start()
        thread.join(timeout=2.0)
        
        # Thread should exit quickly
        assert not thread.is_alive()
    
    def test_empty_queue(self, test_db, scan_run_id, results_queue, shutdown_event):
        """Test writer thread handles empty queue."""
        # Only add sentinel
        results_queue.put(None)
        
        # Run writer thread
        thread = threading.Thread(
            target=writer_thread_main,
            args=(results_queue, str(test_db), scan_run_id, 100, shutdown_event),
        )
        thread.start()
        thread.join(timeout=2.0)
        
        assert not thread.is_alive()
        
        # Verify no items written
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        cursor = conn.execute("SELECT COUNT(*) FROM media_items")
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 0


class TestWriteBatch:
    """Tests for _write_batch function."""
    
    def test_write_batch_media_items(self, test_db, scan_run_id):
        """Test writing a batch of media items."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        from gphotos_321sync.media_scanner.dal.media_items import MediaItemDAL
        from gphotos_321sync.media_scanner.dal.processing_errors import ProcessingErrorDAL
        
        media_dal = MediaItemDAL(conn)
        error_dal = ProcessingErrorDAL(conn)
        
        import uuid
        batch = [
            {
                "type": "media_item",
                "record": {
                    "media_item_id": str(uuid.uuid4()),
                    "relative_path": "Photos/test1.jpg",
                    "album_id": "album-123",
                    "file_size": 1000,
                    "mime_type": "image/jpeg",
                    "scan_run_id": scan_run_id,
                    "status": "present",
                }
            },
            {
                "type": "media_item",
                "record": {
                    "media_item_id": str(uuid.uuid4()),
                    "relative_path": "Photos/test2.jpg",
                    "album_id": "album-123",
                    "file_size": 2000,
                    "mime_type": "image/jpeg",
                    "scan_run_id": scan_run_id,
                    "status": "present",
                }
            },
        ]
        
        _write_batch(batch, media_dal, error_dal, conn)
        
        # Verify items written
        cursor = conn.execute("SELECT COUNT(*) FROM media_items")
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 2
    
    def test_write_batch_empty(self, test_db, scan_run_id):
        """Test writing an empty batch."""
        db_conn = DatabaseConnection(test_db)
        conn = db_conn.connect()
        
        from gphotos_321sync.media_scanner.dal.media_items import MediaItemDAL
        from gphotos_321sync.media_scanner.dal.processing_errors import ProcessingErrorDAL
        
        media_dal = MediaItemDAL(conn)
        error_dal = ProcessingErrorDAL(conn)
        
        # Should not raise error
        _write_batch([], media_dal, error_dal, conn)
        
        conn.close()
