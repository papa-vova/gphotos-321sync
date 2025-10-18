"""Worker thread for parallel media scanning.

Worker threads coordinate I/O-bound and CPU-bound work:
1. Pull FileInfo from work queue
2. Submit CPU work to process pool
3. Coordinate metadata (I/O work)
4. Put result in results queue

Architecture:
- N worker threads (2× CPU cores for I/O overlap)
- M worker processes (1× CPU cores for CPU parallelism)
- Work queue: FileInfo objects
- Results queue: MediaItemRecord or error dicts
"""

import logging
from multiprocessing.pool import Pool
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Dict, Optional

from ..discovery import FileInfo
from ..errors import classify_error
from ..file_processor import process_file_cpu_work
from ..metadata_coordinator import coordinate_metadata

logger = logging.getLogger(__name__)


class WorkerThreadShutdown(Exception):
    """Signal to worker thread to shut down gracefully."""
    pass


def worker_thread_main(
    thread_id: int,
    work_queue: Queue,
    results_queue: Queue,
    process_pool: Pool,
    scan_run_id: str,
    use_exiftool: bool,
    use_ffprobe: bool,
    shutdown_event: Any,  # threading.Event
) -> None:
    """Main function for worker thread.
    
    Args:
        thread_id: Unique identifier for this worker thread
        work_queue: Queue of (FileInfo, album_id) tuples to process
        results_queue: Queue for results (MediaItemRecord or error dict)
        process_pool: Multiprocessing pool for CPU work
        scan_run_id: Current scan run UUID
        use_exiftool: Whether to use exiftool for EXIF extraction
        use_ffprobe: Whether to use ffprobe for video metadata
        shutdown_event: Event to signal shutdown
    
    Returns:
        None (runs until shutdown_event is set or queue is empty)
    """
    logger.info(f"Worker thread {thread_id} started")
    
    processed_count = 0
    error_count = 0
    
    try:
        while not shutdown_event.is_set():
            try:
                # Get work from queue with timeout to check shutdown event
                work_item = work_queue.get(timeout=0.1)
                
                # Check for sentinel value (shutdown signal)
                if work_item is None:
                    logger.debug(f"Worker thread {thread_id} received shutdown sentinel")
                    break
                
                file_info, album_id = work_item
                
                try:
                    # Process the file
                    result = _process_file_work(
                        file_info=file_info,
                        album_id=album_id,
                        process_pool=process_pool,
                        scan_run_id=scan_run_id,
                        use_exiftool=use_exiftool,
                        use_ffprobe=use_ffprobe,
                    )
                    
                    # Put result in results queue
                    results_queue.put(result)
                    processed_count += 1
                    
                except Exception as e:
                    # Handle processing errors
                    error_result = {
                        "type": "error",
                        "file_path": str(file_info.file_path),
                        "relative_path": file_info.relative_path,
                        "error_type": "media_file",
                        "error_category": classify_error(e),
                        "error_message": str(e),
                        "scan_run_id": scan_run_id,
                    }
                    results_queue.put(error_result)
                    error_count += 1
                    
                    logger.error(
                        f"Worker {thread_id} failed to process {file_info.relative_path}: {e}",
                        exc_info=True
                    )
                
                finally:
                    # Mark task as done
                    work_queue.task_done()
                    
            except Empty:
                # Queue is empty, check shutdown event and continue
                continue
                
    except Exception as e:
        logger.error(f"Worker thread {thread_id} crashed: {e}", exc_info=True)
        raise
    
    finally:
        logger.info(
            f"Worker thread {thread_id} shutting down "
            f"(processed={processed_count}, errors={error_count})"
        )


def _process_file_work(
    file_info: FileInfo,
    album_id: str,
    process_pool: Pool,
    scan_run_id: str,
    use_exiftool: bool,
    use_ffprobe: bool,
) -> Dict[str, Any]:
    """Process a single file (CPU work + I/O work).
    
    Args:
        file_info: File information from discovery
        album_id: Album UUID for this file
        process_pool: Process pool for CPU work
        scan_run_id: Current scan run UUID
        use_exiftool: Whether to use exiftool
        use_ffprobe: Whether to use ffprobe
    
    Returns:
        MediaItemRecord dict or error dict
    
    Raises:
        Exception: Any processing error (caught by caller)
    """
    # Submit CPU work to process pool
    # This runs in a separate process for true parallelism
    cpu_future = process_pool.apply_async(
        process_file_cpu_work,
        (
            file_info.file_path,
            file_info.file_size,
            use_exiftool,
            use_ffprobe,
        )
    )
    
    # Wait for CPU work to complete
    # Worker thread blocks here, but other threads continue working
    metadata_ext = cpu_future.get()
    
    # Check if CPU work resulted in an error
    if metadata_ext.get("error"):
        # Return error result
        return {
            "type": "error",
            "file_path": str(file_info.file_path),
            "relative_path": file_info.relative_path,
            "error_type": "media_file",
            "error_category": metadata_ext["error_category"],
            "error_message": metadata_ext["error_message"],
            "scan_run_id": scan_run_id,
        }
    
    # Coordinate metadata (I/O work - parse JSON sidecar)
    # This runs in the worker thread (I/O-bound)
    media_item_record = coordinate_metadata(
        file_info=file_info,
        metadata_ext=metadata_ext,
        album_id=album_id,
        scan_run_id=scan_run_id,
    )
    
    # Return success result
    return {
        "type": "media_item",
        "record": media_item_record,
    }


def worker_thread_batch_main(
    thread_id: int,
    work_queue: Queue,
    results_queue: Queue,
    process_pool: Pool,
    scan_run_id: str,
    use_exiftool: bool,
    use_ffprobe: bool,
    shutdown_event: Any,
    batch_size: int = 10,
) -> None:
    """Worker thread with batch submission to process pool.
    
    This version submits work in batches to keep the process pool saturated.
    More efficient than submitting one job at a time.
    
    Args:
        thread_id: Unique identifier for this worker thread
        work_queue: Queue of (FileInfo, album_id) tuples
        results_queue: Queue for results
        process_pool: Multiprocessing pool for CPU work
        scan_run_id: Current scan run UUID
        use_exiftool: Whether to use exiftool
        use_ffprobe: Whether to use ffprobe
        shutdown_event: Event to signal shutdown
        batch_size: Number of jobs to submit to pool at once
    """
    logger.info(f"Worker thread {thread_id} started (batch mode, batch_size={batch_size})")
    
    processed_count = 0
    error_count = 0
    
    shutdown_received = False
    
    try:
        while not shutdown_event.is_set() and not shutdown_received:
            # Collect a batch of work items
            batch = []
            
            for _ in range(batch_size):
                try:
                    work_item = work_queue.get(timeout=0.1)
                    
                    # Check for sentinel
                    if work_item is None:
                        logger.debug(f"Worker thread {thread_id} received shutdown sentinel")
                        # Put sentinel back for other workers
                        work_queue.put(None)
                        shutdown_received = True
                        break
                    
                    batch.append(work_item)
                    
                except Empty:
                    # No more work available right now
                    break
            
            # If no work collected, check if we should exit
            if not batch:
                if shutdown_received:
                    break
                continue
            
            # Submit batch to process pool
            futures = []
            for file_info, album_id in batch:
                future = process_pool.apply_async(
                    process_file_cpu_work,
                    (
                        file_info.file_path,
                        file_info.file_size,
                        use_exiftool,
                        use_ffprobe,
                    )
                )
                futures.append((future, file_info, album_id))
            
            # Drain results asynchronously
            for future, file_info, album_id in futures:
                try:
                    metadata_ext = future.get()
                    
                    # Check for CPU errors
                    if metadata_ext.get("error"):
                        error_result = {
                            "type": "error",
                            "file_path": str(file_info.file_path),
                            "relative_path": file_info.relative_path,
                            "error_type": "media_file",
                            "error_category": metadata_ext["error_category"],
                            "error_message": metadata_ext["error_message"],
                            "scan_run_id": scan_run_id,
                        }
                        results_queue.put(error_result)
                        error_count += 1
                    else:
                        # Coordinate metadata
                        media_item_record = coordinate_metadata(
                            file_info=file_info,
                            metadata_ext=metadata_ext,
                            album_id=album_id,
                            scan_run_id=scan_run_id,
                        )
                        
                        results_queue.put({
                            "type": "media_item",
                            "record": media_item_record,
                        })
                        processed_count += 1
                        
                except Exception as e:
                    error_result = {
                        "type": "error",
                        "file_path": str(file_info.file_path),
                        "relative_path": file_info.relative_path,
                        "error_type": "media_file",
                        "error_category": classify_error(e),
                        "error_message": str(e),
                        "scan_run_id": scan_run_id,
                    }
                    results_queue.put(error_result)
                    error_count += 1
                    
                    logger.error(
                        f"Worker {thread_id} failed to process {file_info.relative_path}: {e}",
                        exc_info=True
                    )
                
                finally:
                    work_queue.task_done()
            
    except Exception as e:
        logger.error(f"Worker thread {thread_id} crashed: {e}", exc_info=True)
        raise
    
    finally:
        logger.info(
            f"Worker thread {thread_id} shutting down "
            f"(processed={processed_count}, errors={error_count})"
        )
