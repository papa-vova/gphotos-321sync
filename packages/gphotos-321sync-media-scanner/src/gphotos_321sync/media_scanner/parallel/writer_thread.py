"""Batch writer thread for parallel media scanning.

The writer thread is responsible for:
1. Reading results from the results queue
2. Batching database writes for efficiency
3. Managing transactions (BEGIN...COMMIT)
4. Updating scan run progress
5. Recording errors in the database

Architecture:
- Single writer thread (SQLite WAL mode, no concurrent writes)
- Batch size: 100-500 records per transaction
- Progress updates: Every 100 files
"""

import logging
import time
from queue import Empty, Queue
from typing import Any, Dict, Optional

from ..dal.media_items import MediaItemDAL
from ..dal.processing_errors import ProcessingErrorDAL
from ..dal.scan_runs import ScanRunDAL
from ..database import DatabaseConnection

logger = logging.getLogger(__name__)


def writer_thread_main(
    results_queue: Queue,
    db_path: str,
    scan_run_id: str,
    batch_size: int,
    shutdown_event: Any,  # threading.Event
    progress_interval: int = 100,
    progress_tracker: Optional[Any] = None,  # ProgressTracker
) -> None:
    """Main function for batch writer thread.
    
    Args:
        results_queue: Queue of results to write (MediaItemRecord or error dicts)
        db_path: Path to SQLite database
        scan_run_id: Current scan run UUID
        batch_size: Number of records to batch per transaction
        shutdown_event: Event to signal shutdown
        progress_interval: Update progress every N files
        progress_tracker: Optional progress tracker for detailed progress logging
    
    Returns:
        None (runs until shutdown_event is set and queue is empty)
    """
    logger.info(f"Writer thread started (batch_size={batch_size})")
    
    # Connect to database
    from pathlib import Path
    db_conn = DatabaseConnection(Path(db_path))
    conn = db_conn.connect()
    
    # Create DAL instances
    media_dal = MediaItemDAL(conn)
    error_dal = ProcessingErrorDAL(conn)
    scan_run_dal = ScanRunDAL(conn)
    
    total_written = 0
    total_errors = 0
    batch = []
    
    try:
        while not shutdown_event.is_set() or not results_queue.empty():
            try:
                # Get result from queue with timeout
                result = results_queue.get(timeout=0.1)
                
                # Check for sentinel value (shutdown signal)
                if result is None:
                    logger.debug("Writer thread received shutdown sentinel")
                    # Mark sentinel as done
                    results_queue.task_done()
                    # Flush remaining batch
                    if batch:
                        _write_batch(batch, media_dal, error_dal, conn)
                        total_written += len([r for r in batch if r["type"] == "media_item"])
                        total_errors += len([r for r in batch if r["type"] == "error"])
                        batch.clear()
                    break
                
                # Add to batch
                batch.append(result)
                
                # Write batch if full
                if len(batch) >= batch_size:
                    _write_batch(batch, media_dal, error_dal, conn)
                    
                    # Update counters
                    media_items = len([r for r in batch if r["type"] == "media_item"])
                    errors = len([r for r in batch if r["type"] == "error"])
                    total_written += media_items
                    total_errors += errors
                    
                    # Update progress
                    if total_written % progress_interval == 0:
                        scan_run_dal.update_scan_run(
                            scan_run_id=scan_run_id,
                            files_processed=total_written,
                        )
                        # Use progress tracker if available (shows ETA and rate)
                        if progress_tracker:
                            progress_tracker.update(total_written)
                        else:
                            logger.info(
                                f"Progress: {total_written} files processed, {total_errors} errors"
                            )
                    
                    batch.clear()
                
                # Mark task as done
                results_queue.task_done()
                
            except Empty:
                # Queue is empty, check if we should flush partial batch
                if batch and shutdown_event.is_set():
                    _write_batch(batch, media_dal, error_dal, conn)
                    total_written += len([r for r in batch if r["type"] == "media_item"])
                    total_errors += len([r for r in batch if r["type"] == "error"])
                    batch.clear()
                continue
        
        # Flush any remaining items
        if batch:
            _write_batch(batch, media_dal, error_dal, conn)
            total_written += len([r for r in batch if r["type"] == "media_item"])
            total_errors += len([r for r in batch if r["type"] == "error"])
        
        # Final progress update
        scan_run_dal.update_scan_run(
            scan_run_id=scan_run_id,
            files_processed=total_written,
            error_files=total_errors,
        )
        
    except Exception as e:
        logger.error(f"Writer thread crashed: {e}", exc_info=True)
        raise
    
    finally:
        conn.close()
        logger.info(
            f"Writer thread shutting down "
            f"(written={total_written}, errors={total_errors})"
        )


def _write_batch(
    batch: list,
    media_dal: MediaItemDAL,
    error_dal: ProcessingErrorDAL,
    conn: Any,
) -> None:
    """Write a batch of results to database.
    
    Args:
        batch: List of result dicts (media items or errors)
        media_dal: MediaItemDAL instance
        error_dal: ProcessingErrorDAL instance
        conn: Database connection
    
    Raises:
        Exception: Any database error (caller handles retry)
    """
    if not batch:
        return
    
    # Note: No explicit BEGIN - SQLite starts implicit transaction on first write
    # We just commit at the end to batch all writes together
    
    try:
        for result in batch:
            if result["type"] == "media_item":
                # Insert media item (no commit - we batch commit at the end)
                record = result["record"]
                media_dal.insert_media_item(record)
                
            elif result["type"] == "error":
                # Insert error record
                error_dal.insert_error(
                    scan_run_id=result["scan_run_id"],
                    relative_path=result["relative_path"],
                    error_type=result["error_type"],
                    error_category=result["error_category"],
                    error_message=result["error_message"],
                )
            else:
                logger.warning(f"Unknown result type: {result['type']}")
        
        # Commit transaction
        conn.commit()
        
    except Exception as e:
        # Rollback on error
        conn.rollback()
        logger.error(f"Failed to write batch of {len(batch)} items: {e}", exc_info=True)
        # Log first item for debugging
        if batch:
            logger.error(f"First item in failed batch: {batch[0]}")
        raise


def writer_thread_with_retry(
    results_queue: Queue,
    db_path: str,
    scan_run_id: str,
    batch_size: int,
    shutdown_event: Any,
    progress_interval: int = 100,
    max_retries: int = 3,
) -> None:
    """Writer thread with retry logic for database errors.
    
    This version retries failed batches with exponential backoff.
    Useful for handling transient database lock errors.
    
    Args:
        results_queue: Queue of results to write
        db_path: Path to SQLite database
        scan_run_id: Current scan run UUID
        batch_size: Number of records per batch
        shutdown_event: Event to signal shutdown
        progress_interval: Update progress every N files
        max_retries: Maximum retry attempts for failed batches
    """
    logger.info(f"Writer thread started with retry (batch_size={batch_size}, max_retries={max_retries})")
    
    from pathlib import Path
    db_conn = DatabaseConnection(Path(db_path))
    conn = db_conn.connect()
    
    media_dal = MediaItemDAL(conn)
    error_dal = ProcessingErrorDAL(conn)
    scan_run_dal = ScanRunDAL(conn)
    
    total_written = 0
    total_errors = 0
    batch = []
    
    try:
        while not shutdown_event.is_set() or not results_queue.empty():
            try:
                result = results_queue.get(timeout=0.1)
                
                if result is None:
                    if batch:
                        _write_batch_with_retry(
                            batch, media_dal, error_dal, conn, max_retries
                        )
                        total_written += len([r for r in batch if r["type"] == "media_item"])
                        total_errors += len([r for r in batch if r["type"] == "error"])
                    break
                
                batch.append(result)
                
                if len(batch) >= batch_size:
                    _write_batch_with_retry(
                        batch, media_dal, error_dal, conn, max_retries
                    )
                    
                    media_items = len([r for r in batch if r["type"] == "media_item"])
                    errors = len([r for r in batch if r["type"] == "error"])
                    total_written += media_items
                    total_errors += errors
                    
                    if total_written % progress_interval == 0:
                        scan_run_dal.update_scan_run(
                            scan_run_id=scan_run_id,
                            files_processed=total_written,
                        )
                        logger.info(
                            f"Progress: {total_written} files processed, {total_errors} errors"
                        )
                    
                    batch.clear()
                
                results_queue.task_done()
                
            except Empty:
                if batch and shutdown_event.is_set():
                    _write_batch_with_retry(
                        batch, media_dal, error_dal, conn, max_retries
                    )
                    total_written += len([r for r in batch if r["type"] == "media_item"])
                    total_errors += len([r for r in batch if r["type"] == "error"])
                    batch.clear()
                continue
        
        if batch:
            _write_batch_with_retry(
                batch, media_dal, error_dal, conn, max_retries
            )
            total_written += len([r for r in batch if r["type"] == "media_item"])
            total_errors += len([r for r in batch if r["type"] == "error"])
        
        scan_run_dal.update_scan_run(
            scan_run_id=scan_run_id,
            files_processed=total_written,
            error_files=total_errors,
        )
        
    except Exception as e:
        logger.error(f"Writer thread crashed: {e}", exc_info=True)
        raise
    
    finally:
        conn.close()
        logger.info(
            f"Writer thread shutting down "
            f"(written={total_written}, errors={total_errors})"
        )


def _write_batch_with_retry(
    batch: list,
    media_dal: MediaItemDAL,
    error_dal: ProcessingErrorDAL,
    conn: Any,
    max_retries: int,
) -> None:
    """Write batch with exponential backoff retry.
    
    Args:
        batch: List of result dicts
        media_dal: MediaItemDAL instance
        error_dal: ProcessingErrorDAL instance
        conn: Database connection
        max_retries: Maximum retry attempts
    
    Raises:
        Exception: If all retries fail
    """
    for attempt in range(max_retries):
        try:
            _write_batch(batch, media_dal, error_dal, conn)
            return  # Success
        except Exception as e:
            if attempt < max_retries - 1:
                # Exponential backoff: 0.1s, 0.2s, 0.4s, ...
                wait_time = 0.1 * (2 ** attempt)
                logger.warning(
                    f"Batch write failed (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {wait_time}s: {e}"
                )
                time.sleep(wait_time)
            else:
                # Final attempt failed
                logger.error(f"Batch write failed after {max_retries} attempts: {e}")
                raise
