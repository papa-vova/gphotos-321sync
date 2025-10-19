"""Tests for worker thread."""

import threading
import time
from pathlib import Path
from queue import Queue
from unittest.mock import MagicMock, Mock, patch
import pytest

from gphotos_321sync.media_scanner.discovery import FileInfo
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
def sample_file_info(tmp_path):
    """Create sample FileInfo."""
    file_path = tmp_path / "test.jpg"
    file_path.write_text("test content", encoding='utf-8')
    
    return FileInfo(
        file_path=file_path,
        relative_path="Photos/test.jpg",
        file_size=12,
        json_sidecar_path=None,
        album_folder_path=Path("Photos"),
    )


class TestProcessFileWork:
    """Tests for _process_file_work function."""
    
    def test_successful_processing(self, sample_file_info, mock_process_pool):
        """Test successful file processing."""
        # Mock CPU result
        metadata_ext = {
            "mime_type": "image/jpeg",
            "file_size": 12,
            "crc32": "abc123",
            "content_fingerprint": "def456",
            "width": 1920,
            "height": 1080,
        }
        
        # Mock process pool
        future = MagicMock()
        future.get.return_value = metadata_ext
        mock_process_pool.apply_async.return_value = future
        
        # Mock coordinate_metadata
        with patch("gphotos_321sync.media_scanner.parallel.worker_thread.coordinate_metadata") as mock_coord:
            mock_coord.return_value = {
                "media_item_id": "item-123",
                "relative_path": "Photos/test.jpg",
                "album_id": "album-456",
            }
            
            result = _process_file_work(
                file_info=sample_file_info,
                album_id="album-456",
                process_pool=mock_process_pool,
                scan_run_id="scan-789",
                use_exiftool=False,
                use_ffprobe=True,
            )
        
        # Verify result
        assert result["type"] == "media_item"
        assert result["record"]["media_item_id"] == "item-123"
        
        # Verify CPU work was submitted
        mock_process_pool.apply_async.assert_called_once()
        args = mock_process_pool.apply_async.call_args[0]
        assert args[1][0] == sample_file_info.file_path
        assert args[1][1] == sample_file_info.file_size
        assert args[1][2] is False  # use_exiftool
        assert args[1][3] is True   # use_ffprobe
    
    def test_cpu_error_handling(self, sample_file_info, mock_process_pool):
        """Test handling of CPU processing errors."""
        # Mock CPU error result
        metadata_ext = {
            "error": True,
            "error_category": "corrupted",
            "error_message": "File is corrupted",
        }
        
        future = MagicMock()
        future.get.return_value = metadata_ext
        mock_process_pool.apply_async.return_value = future
        
        result = _process_file_work(
            file_info=sample_file_info,
            album_id="album-456",
            process_pool=mock_process_pool,
            scan_run_id="scan-789",
            use_exiftool=False,
            use_ffprobe=False,
        )
        
        # Verify error result
        assert result["type"] == "error"
        assert result["error_category"] == "corrupted"
        assert result["error_message"] == "File is corrupted"
        assert result["relative_path"] == "Photos/test.jpg"


class TestWorkerThreadMain:
    """Tests for worker_thread_main function."""
    
    def test_processes_single_item(
        self,
        sample_file_info,
        work_queue,
        results_queue,
        mock_process_pool,
        shutdown_event,
    ):
        """Test worker thread processes a single item."""
        # Add work to queue
        work_queue.put((sample_file_info, "album-456"))
        work_queue.put(None)  # Sentinel to stop
        
        # Mock CPU result
        metadata_ext = {
            "mime_type": "image/jpeg",
            "file_size": 12,
            "crc32": "abc123",
            "content_fingerprint": "def456",
        }
        future = MagicMock()
        future.get.return_value = metadata_ext
        mock_process_pool.apply_async.return_value = future
        
        # Mock coordinate_metadata
        with patch("gphotos_321sync.media_scanner.parallel.worker_thread.coordinate_metadata") as mock_coord:
            mock_coord.return_value = {
                "media_item_id": "item-123",
                "relative_path": "Photos/test.jpg",
            }
            
            # Run worker thread in actual thread
            thread = threading.Thread(
                target=worker_thread_main,
                args=(
                    1,
                    work_queue,
                    results_queue,
                    mock_process_pool,
                    "scan-789",
                    False,
                    False,
                    shutdown_event,
                ),
            )
            thread.start()
            thread.join(timeout=2.0)  # Wait max 2 seconds
            
            # Thread should have finished
            assert not thread.is_alive()
        
        # Verify result was put in queue
        assert results_queue.qsize() == 1
        result = results_queue.get()
        assert result["type"] == "media_item"
        assert result["record"]["media_item_id"] == "item-123"
    
    def test_handles_processing_error(
        self,
        sample_file_info,
        work_queue,
        results_queue,
        mock_process_pool,
        shutdown_event,
    ):
        """Test worker thread handles processing errors."""
        work_queue.put((sample_file_info, "album-456"))
        work_queue.put(None)
        
        # Mock process pool to raise exception
        mock_process_pool.apply_async.side_effect = RuntimeError("Processing failed")
        
        # Run worker thread in actual thread
        thread = threading.Thread(
            target=worker_thread_main,
            args=(1, work_queue, results_queue, mock_process_pool, "scan-789", False, False, shutdown_event),
        )
        thread.start()
        thread.join(timeout=2.0)
        assert not thread.is_alive()
        
        # Verify error was recorded
        assert results_queue.qsize() == 1
        result = results_queue.get()
        assert result["type"] == "error"
        assert "Processing failed" in result["error_message"]
    
    def test_shutdown_event(
        self,
        work_queue,
        results_queue,
        mock_process_pool,
        shutdown_event,
    ):
        """Test worker thread respects shutdown event."""
        # Set shutdown event immediately
        shutdown_event.set()
        
        # Run worker thread in actual thread
        thread = threading.Thread(
            target=worker_thread_main,
            args=(1, work_queue, results_queue, mock_process_pool, "scan-789", False, False, shutdown_event),
        )
        thread.start()
        thread.join(timeout=2.0)
        assert not thread.is_alive()
        
        # Verify no results (thread shut down immediately)
        assert results_queue.qsize() == 0
    
    def test_processes_multiple_items(
        self,
        tmp_path,
        work_queue,
        results_queue,
        mock_process_pool,
        shutdown_event,
    ):
        """Test worker thread processes multiple items."""
        # Create multiple files
        files = []
        for i in range(3):
            file_path = tmp_path / f"test{i}.jpg"
            file_path.write_text(f"content {i}", encoding='utf-8')
            file_info = FileInfo(
                file_path=file_path,
                relative_path=f"Photos/test{i}.jpg",
                file_size=len(f"content {i}"),
                json_sidecar_path=None,
                album_folder_path=Path("Photos"),
            )
            files.append(file_info)
            work_queue.put((file_info, f"album-{i}"))
        
        work_queue.put(None)  # Sentinel
        
        # Mock CPU results
        metadata_ext = {"mime_type": "image/jpeg", "file_size": 10}
        future = MagicMock()
        future.get.return_value = metadata_ext
        mock_process_pool.apply_async.return_value = future
        
        # Mock coordinate_metadata
        with patch("gphotos_321sync.media_scanner.parallel.worker_thread.coordinate_metadata") as mock_coord:
            mock_coord.side_effect = [
                {"media_item_id": f"item-{i}"} for i in range(3)
            ]
            
            thread = threading.Thread(
                target=worker_thread_main,
                args=(1, work_queue, results_queue, mock_process_pool, "scan-789", False, False, shutdown_event),
            )
            thread.start()
            thread.join(timeout=2.0)
            assert not thread.is_alive()
        
        # Verify all items processed
        assert results_queue.qsize() == 3
        for i in range(3):
            result = results_queue.get()
            assert result["type"] == "media_item"
    
    def test_task_done_called(
        self,
        sample_file_info,
        work_queue,
        results_queue,
        mock_process_pool,
        shutdown_event,
    ):
        """Test that task_done is called for each work item."""
        work_queue.put((sample_file_info, "album-456"))
        work_queue.put(None)
        
        # Mock CPU result
        metadata_ext = {"mime_type": "image/jpeg"}
        future = MagicMock()
        future.get.return_value = metadata_ext
        mock_process_pool.apply_async.return_value = future
        
        with patch("gphotos_321sync.media_scanner.parallel.worker_thread.coordinate_metadata") as mock_coord:
            mock_coord.return_value = {"media_item_id": "item-123"}
            
            thread = threading.Thread(
                target=worker_thread_main,
                args=(1, work_queue, results_queue, mock_process_pool, "scan-789", False, False, shutdown_event),
            )
            thread.start()
            thread.join(timeout=2.0)
            assert not thread.is_alive()
        
        # Verify queue is empty and all tasks marked done
        assert work_queue.qsize() == 0


class TestWorkerThreadBatchMain:
    """Tests for worker_thread_batch_main function."""
    
    def test_batch_processing(
        self,
        tmp_path,
        work_queue,
        results_queue,
        mock_process_pool,
        shutdown_event,
    ):
        """Test batch processing of multiple items."""
        # Create batch of files
        batch_size = 5
        for i in range(batch_size):
            file_path = tmp_path / f"test{i}.jpg"
            file_path.write_text(f"content {i}", encoding='utf-8')
            file_info = FileInfo(
                file_path=file_path,
                relative_path=f"Photos/test{i}.jpg",
                file_size=len(f"content {i}"),
                json_sidecar_path=None,
                album_folder_path=Path("Photos"),
            )
            work_queue.put((file_info, f"album-{i}"))
        
        work_queue.put(None)  # Sentinel
        
        # Mock CPU results
        metadata_ext = {"mime_type": "image/jpeg"}
        future = MagicMock()
        future.get.return_value = metadata_ext
        mock_process_pool.apply_async.return_value = future
        
        # Mock coordinate_metadata
        with patch("gphotos_321sync.media_scanner.parallel.worker_thread.coordinate_metadata") as mock_coord:
            mock_coord.side_effect = [
                {"media_item_id": f"item-{i}"} for i in range(batch_size)
            ]
            
            thread = threading.Thread(
                target=worker_thread_batch_main,
                args=(1, work_queue, results_queue, mock_process_pool, "scan-789", False, False, shutdown_event, batch_size),
            )
            thread.start()
            thread.join(timeout=2.0)
            assert not thread.is_alive()
        
        # Verify all items processed
        assert results_queue.qsize() == batch_size
        
        # Verify process pool was called for each item
        assert mock_process_pool.apply_async.call_count == batch_size
    
    def test_batch_with_errors(
        self,
        tmp_path,
        work_queue,
        results_queue,
        mock_process_pool,
        shutdown_event,
    ):
        """Test batch processing with some errors."""
        # Create files
        for i in range(3):
            file_path = tmp_path / f"test{i}.jpg"
            file_path.write_text(f"content {i}", encoding='utf-8')
            file_info = FileInfo(
                file_path=file_path,
                relative_path=f"Photos/test{i}.jpg",
                file_size=len(f"content {i}"),
                json_sidecar_path=None,
                album_folder_path=Path("Photos"),
            )
            work_queue.put((file_info, f"album-{i}"))
        
        work_queue.put(None)
        
        # Mock CPU results - one success, one error, one exception
        results = [
            {"mime_type": "image/jpeg"},  # Success
            {"error": True, "error_category": "corrupted", "error_message": "Corrupted"},  # CPU error
            {"mime_type": "image/jpeg"},  # Success
        ]
        
        futures = []
        for result in results:
            future = MagicMock()
            future.get.return_value = result
            futures.append(future)
        
        mock_process_pool.apply_async.side_effect = futures
        
        # Mock coordinate_metadata - will only be called for successes
        with patch("gphotos_321sync.media_scanner.parallel.worker_thread.coordinate_metadata") as mock_coord:
            mock_coord.side_effect = [
                {"media_item_id": "item-0"},
                {"media_item_id": "item-2"},
            ]
            
            thread = threading.Thread(
                target=worker_thread_batch_main,
                args=(1, work_queue, results_queue, mock_process_pool, "scan-789", False, False, shutdown_event, 10),
            )
            thread.start()
            thread.join(timeout=2.0)
            assert not thread.is_alive()
        
        # Verify results: 2 successes + 1 error
        assert results_queue.qsize() == 3
        
        result_types = []
        for _ in range(3):
            result = results_queue.get()
            result_types.append(result["type"])
        
        assert result_types.count("media_item") == 2
        assert result_types.count("error") == 1
    
    def test_partial_batch(
        self,
        tmp_path,
        work_queue,
        results_queue,
        mock_process_pool,
        shutdown_event,
    ):
        """Test batch processing with fewer items than batch size."""
        # Add only 2 items with batch size of 10
        for i in range(2):
            file_path = tmp_path / f"test{i}.jpg"
            file_path.write_text(f"content {i}", encoding='utf-8')
            file_info = FileInfo(
                file_path=file_path,
                relative_path=f"Photos/test{i}.jpg",
                file_size=len(f"content {i}"),
                json_sidecar_path=None,
                album_folder_path=Path("Photos"),
            )
            work_queue.put((file_info, f"album-{i}"))
        
        work_queue.put(None)
        
        # Mock CPU results
        metadata_ext = {"mime_type": "image/jpeg"}
        future = MagicMock()
        future.get.return_value = metadata_ext
        mock_process_pool.apply_async.return_value = future
        
        with patch("gphotos_321sync.media_scanner.parallel.worker_thread.coordinate_metadata") as mock_coord:
            mock_coord.side_effect = [
                {"media_item_id": f"item-{i}"} for i in range(2)
            ]
            
            thread = threading.Thread(
                target=worker_thread_batch_main,
                args=(1, work_queue, results_queue, mock_process_pool, "scan-789", False, False, shutdown_event, 10),
            )
            thread.start()
            thread.join(timeout=2.0)
            assert not thread.is_alive()
        
        # Verify both items processed despite small batch
        assert results_queue.qsize() == 2
