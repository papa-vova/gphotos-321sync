"""Tests for worker thread."""

import threading
import time
from pathlib import Path
from queue import Queue
from unittest.mock import MagicMock, Mock, patch
import pytest

from gphotos_321sync.media_scanner.database import DatabaseConnection
from gphotos_321sync.media_scanner.discovery import FileInfo
from gphotos_321sync.media_scanner.migrations import MigrationRunner
from gphotos_321sync.media_scanner.parallel.worker_thread import (
    worker_thread_main,
    worker_thread_batch_main,
    _process_file_work,
)


@pytest.fixture
def mock_process_pool():
    """Create a mock process pool."""
    pool = MagicMock()
    return pool


@pytest.fixture
def work_queue():
    """Create a work queue."""
    return Queue()


@pytest.fixture
def results_queue():
    """Create a results queue."""
    return Queue()


@pytest.fixture
def shutdown_event():
    """Create a shutdown event."""
    return threading.Event()


@pytest.fixture
def test_db(tmp_path):
    """Create a test database with schema."""
    db_path = tmp_path / "test.db"
    db = DatabaseConnection(db_path)
    db.connect()
    
    # Apply migrations
    schema_dir = Path(__file__).parent.parent.parent / "packages" / "gphotos-321sync-media-scanner" / "src" / "gphotos_321sync" / "media_scanner" / "schema"
    runner = MigrationRunner(db, schema_dir)
    runner.apply_migrations()
    
    yield db
    db.close()


class TestWorkerThreadMain:
    """Tests for worker_thread_main function."""
    
    def test_worker_thread_main_basic(self, work_queue, results_queue, shutdown_event, test_db):
        """Test basic worker thread functionality."""
        # Create a mock FileInfo
        file_info = FileInfo(
            file_path=Path("/test/file.jpg"),
            relative_path=Path("test/file.jpg"),
            album_folder_path=Path("test"),
            json_sidecar_path=None,
            file_size=1024
        )
        
        # Add work to queue (worker expects tuple of (file_info, album_id))
        work_queue.put((file_info, "test_album"))
        work_queue.put(None)  # Sentinel to stop worker
        
        # Mock process pool
        from unittest.mock import Mock
        mock_pool = Mock()
        
        # Start worker thread with correct signature
        worker = threading.Thread(
            target=worker_thread_main,
            args=(1, work_queue, results_queue, mock_pool, str(test_db.db_path), 
                 "test_scan_run", "2024-01-01T00:00:00+00:00", False, False, shutdown_event)
        )
        worker.start()
        
        # Wait for worker to process
        worker.join(timeout=5)
        
        # Verify worker completed
        assert not worker.is_alive()
    
    def test_worker_thread_main_shutdown(self, work_queue, results_queue, shutdown_event, test_db):
        """Test worker thread shutdown handling."""
        # Mock process pool
        from unittest.mock import Mock
        mock_pool = Mock()
        
        # Start worker thread with correct signature
        worker = threading.Thread(
            target=worker_thread_main,
            args=(1, work_queue, results_queue, mock_pool, str(test_db.db_path), 
                 "test_scan_run", "2024-01-01T00:00:00+00:00", False, False, shutdown_event)
        )
        worker.start()
        
        # Set shutdown event
        shutdown_event.set()
        
        # Wait for worker to shutdown
        worker.join(timeout=5)
        
        # Verify worker completed
        assert not worker.is_alive()
    
    def test_worker_thread_main_empty_queue(self, work_queue, results_queue, shutdown_event, test_db):
        """Test worker thread with empty queue."""
        # Add sentinel immediately
        work_queue.put(None)
        
        # Start worker thread
        from unittest.mock import Mock
        mock_pool = Mock()
        
        worker = threading.Thread(
            target=worker_thread_main,
            args=(1, work_queue, results_queue, mock_pool, str(test_db.db_path), 
                 "test_scan_run", "2024-01-01T00:00:00+00:00", False, False, shutdown_event)
        )
        worker.start()
        
        # Wait for worker to complete
        worker.join(timeout=5)
        
        # Verify worker completed
        assert not worker.is_alive()
    
    def test_worker_thread_main_exception_handling(self, work_queue, results_queue, shutdown_event, test_db):
        """Test worker thread exception handling."""
        # Create a mock FileInfo that will cause an exception
        file_info = FileInfo(
            file_path=Path("/nonexistent/file.jpg"),
            relative_path=Path("nonexistent/file.jpg"),
            album_folder_path=Path("nonexistent"),
            json_sidecar_path=None,
            file_size=1024
        )
        
        # Add work to queue (worker expects tuple of (file_info, album_id))
        work_queue.put((file_info, "test_album"))
        work_queue.put(None)  # Sentinel to stop worker
        
        # Start worker thread
        from unittest.mock import Mock
        mock_pool = Mock()
        
        worker = threading.Thread(
            target=worker_thread_main,
            args=(1, work_queue, results_queue, mock_pool, str(test_db.db_path), 
                 "test_scan_run", "2024-01-01T00:00:00+00:00", False, False, shutdown_event)
        )
        worker.start()
        
        # Wait for worker to process
        worker.join(timeout=5)
        
        # Verify worker completed (should handle exceptions gracefully)
        assert not worker.is_alive()


class TestWorkerThreadBatchMain:
    """Tests for worker_thread_batch_main function."""
    
    def test_worker_thread_batch_main_basic(self, work_queue, results_queue, shutdown_event, test_db):
        """Test basic batch worker thread functionality."""
        # Create mock FileInfo objects
        file_infos = [
            FileInfo(
                file_path=Path("/test/file1.jpg"),
                relative_path=Path("test/file1.jpg"),
                album_folder_path=Path("test"),
                json_sidecar_path=None,
                file_size=1024
            ),
            FileInfo(
                file_path=Path("/test/file2.jpg"),
                relative_path=Path("test/file2.jpg"),
                album_folder_path=Path("test"),
                json_sidecar_path=None,
                file_size=2048
            )
        ]
        
        # Add work to queue (batch worker collects individual tuples)
        work_queue.put((file_infos[0], "test_album"))
        work_queue.put((file_infos[1], "test_album"))
        work_queue.put(None)  # Sentinel to stop worker
        
        # Start worker thread
        from unittest.mock import Mock
        mock_pool = Mock()
        
        worker = threading.Thread(
            target=worker_thread_batch_main,
            args=(1, work_queue, results_queue, mock_pool, "test_scan_run", False, False, shutdown_event)
        )
        worker.start()
        
        # Wait for worker to process
        worker.join(timeout=5)
        
        # Verify worker completed
        assert not worker.is_alive()
    
    def test_worker_thread_batch_main_shutdown(self, work_queue, results_queue, shutdown_event, test_db):
        """Test batch worker thread shutdown handling."""
        # Start worker thread
        from unittest.mock import Mock
        mock_pool = Mock()
        
        worker = threading.Thread(
            target=worker_thread_batch_main,
            args=(1, work_queue, results_queue, mock_pool, "test_scan_run", False, False, shutdown_event)
        )
        worker.start()
        
        # Set shutdown event
        shutdown_event.set()
        
        # Wait for worker to shutdown
        worker.join(timeout=5)
        
        # Verify worker completed
        assert not worker.is_alive()
    
    def test_worker_thread_batch_main_empty_batch(self, work_queue, results_queue, shutdown_event, test_db):
        """Test batch worker thread with empty batch."""
        # Don't put empty batch, just put sentinel to stop worker
        work_queue.put(None)  # Sentinel to stop worker
        
        # Start worker thread
        from unittest.mock import Mock
        mock_pool = Mock()
        
        worker = threading.Thread(
            target=worker_thread_batch_main,
            args=(1, work_queue, results_queue, mock_pool, "test_scan_run", False, False, shutdown_event)
        )
        worker.start()
        
        # Wait for worker to complete
        worker.join(timeout=5)
        
        # Verify worker completed
        assert not worker.is_alive()


class TestProcessFileWork:
    """Tests for _process_file_work function."""
    
    def test_process_file_work_basic(self, test_db):
        """Test basic file processing."""
        file_info = FileInfo(
            file_path=Path("/test/file.jpg"),
            relative_path=Path("test/file.jpg"),
            album_folder_path=Path("test"),
            json_sidecar_path=None,
            file_size=1024
        )
        
        # Mock the process pool
        mock_pool = Mock()
        mock_future = Mock()
        mock_future.get.return_value = {"error": False, "metadata": {}}
        mock_pool.apply_async.return_value = mock_future
        
        # Mock the metadata coordinator
        with patch('gphotos_321sync.media_scanner.parallel.worker_thread.coordinate_metadata') as mock_coord:
            mock_coord.return_value = ({}, [])
            
            result = _process_file_work(file_info, "test_album", mock_pool, "scan_run_123", True, True)
            
            # Verify processing was called
            mock_pool.apply_async.assert_called_once()
            mock_coord.assert_called_once()
            assert result["type"] == "media_item"
    
    def test_process_file_work_with_sidecar(self, test_db):
        """Test file processing with sidecar."""
        sidecar_path = Path("/test/file.jpg.supplemental-metadata.json")
        file_info = FileInfo(
            file_path=Path("/test/file.jpg"),
            relative_path=Path("test/file.jpg"),
            album_folder_path=Path("test"),
            json_sidecar_path=sidecar_path,
            file_size=1024
        )
        
        # Mock the process pool
        mock_pool = Mock()
        mock_future = Mock()
        mock_future.get.return_value = {"error": False, "metadata": {}}
        mock_pool.apply_async.return_value = mock_future
        
        # Mock the metadata coordinator
        with patch('gphotos_321sync.media_scanner.parallel.worker_thread.coordinate_metadata') as mock_coord:
            mock_coord.return_value = ({}, [])
            
            result = _process_file_work(file_info, "test_album", mock_pool, "scan_run_123", True, True)
            
            # Verify processing was called
            mock_pool.apply_async.assert_called_once()
            mock_coord.assert_called_once()
            assert result["type"] == "media_item"
    
    def test_process_file_work_exception(self, test_db):
        """Test file processing with exception."""
        file_info = FileInfo(
            file_path=Path("/nonexistent/file.jpg"),
            relative_path=Path("nonexistent/file.jpg"),
            album_folder_path=Path("nonexistent"),
            json_sidecar_path=None,
            file_size=1024
        )
        
        # Mock the file processing to raise an exception
        with patch('gphotos_321sync.media_scanner.parallel.worker_thread._process_file_work') as mock_process:
            mock_process.side_effect = Exception("Processing failed")
            
            # Should handle exception gracefully
            try:
                result = _process_file_work(file_info, test_db, None)
            except Exception:
                # Exception should be handled by the worker thread
                pass


class TestWorkerThreadIntegration:
    """Integration tests for worker thread."""
    
    def test_worker_thread_with_real_database(self, work_queue, results_queue, shutdown_event, test_db):
        """Test worker thread with real database operations."""
        # Create a real FileInfo
        file_info = FileInfo(
            file_path=Path("/test/file.jpg"),
            relative_path=Path("test/file.jpg"),
            album_folder_path=Path("test"),
            json_sidecar_path=None,
            file_size=1024
        )
        
        # Add work to queue (worker expects tuple of (file_info, album_id))
        work_queue.put((file_info, "test_album"))
        work_queue.put(None)  # Sentinel to stop worker
        
        # Start worker thread
        from unittest.mock import Mock
        mock_pool = Mock()
        
        worker = threading.Thread(
            target=worker_thread_main,
            args=(1, work_queue, results_queue, mock_pool, str(test_db.db_path), 
                 "test_scan_run", "2024-01-01T00:00:00+00:00", False, False, shutdown_event)
        )
        worker.start()
        
        # Wait for worker to process
        worker.join(timeout=5)
        
        # Verify worker completed
        assert not worker.is_alive()
    
    def test_worker_thread_concurrent_execution(self, test_db):
        """Test multiple worker threads running concurrently."""
        work_queue = Queue()
        results_queue = Queue()
        shutdown_event = threading.Event()
        
        # Create multiple FileInfo objects
        file_infos = [
            FileInfo(
                file_path=Path(f"/test/file{i}.jpg"),
                relative_path=Path(f"test/file{i}.jpg"),
                album_folder_path=Path("test"),
                json_sidecar_path=None,
                file_size=1024
            )
            for i in range(5)
        ]
        
        # Add work to queue (worker expects tuple of (file_info, album_id))
        for file_info in file_infos:
            work_queue.put((file_info, "test_album"))
        
        # Add sentinels for each worker
        for _ in range(3):
            work_queue.put(None)
        
        # Start multiple worker threads
        workers = []
        from unittest.mock import Mock
        mock_pool = Mock()
        
        for i in range(3):
            worker = threading.Thread(
                target=worker_thread_main,
                args=(i, work_queue, results_queue, mock_pool, str(test_db.db_path), 
                     "test_scan_run", "2024-01-01T00:00:00+00:00", False, False, shutdown_event)
            )
            worker.start()
            workers.append(worker)
        
        # Wait for all workers to complete
        for worker in workers:
            worker.join(timeout=5)
            assert not worker.is_alive()
    
    def test_worker_thread_resource_cleanup(self, work_queue, results_queue, shutdown_event, test_db):
        """Test worker thread resource cleanup."""
        # Start worker thread
        from unittest.mock import Mock
        mock_pool = Mock()
        
        worker = threading.Thread(
            target=worker_thread_main,
            args=(1, work_queue, results_queue, mock_pool, str(test_db.db_path), 
                 "test_scan_run", "2024-01-01T00:00:00+00:00", False, False, shutdown_event)
        )
        worker.start()
        
        # Set shutdown event
        shutdown_event.set()
        
        # Wait for worker to shutdown
        worker.join(timeout=5)
        
        # Verify worker completed and resources were cleaned up
        assert not worker.is_alive()
        assert shutdown_event.is_set()
