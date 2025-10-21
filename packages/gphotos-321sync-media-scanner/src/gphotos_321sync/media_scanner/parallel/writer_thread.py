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
import sqlite3
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
    logger.info(f"Started writer thread: {{'batch_size': {batch_size}}}")
    
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
    total_new_files = 0
    total_unchanged_files = 0
    total_changed_files = 0
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
                        new_items = len([r for r in batch if r["type"] == "media_item" and not r.get("is_changed", False)])
                        changed_items = len([r for r in batch if r["type"] == "media_item" and r.get("is_changed", False)])
                        unchanged_items = len([r for r in batch if r["type"] == "file_seen"])
                        total_new_files += new_items
                        total_changed_files += changed_items
                        total_unchanged_files += unchanged_items
                        total_written += new_items + changed_items + unchanged_items
                        total_errors += len([r for r in batch if r["type"] == "error"])
                        batch.clear()
                    break
                
                # Add to batch
                batch.append(result)
                
                # Write batch if full
                if len(batch) >= batch_size:
                    _write_batch(batch, media_dal, error_dal, conn)
                    
                    # Update counters
                    new_items = len([r for r in batch if r["type"] == "media_item" and not r.get("is_changed", False)])
                    changed_items = len([r for r in batch if r["type"] == "media_item" and r.get("is_changed", False)])
                    file_seen = len([r for r in batch if r["type"] == "file_seen"])
                    errors = len([r for r in batch if r["type"] == "error"])
                    total_new_files += new_items
                    total_changed_files += changed_items
                    total_unchanged_files += file_seen
                    total_written += new_items + changed_items + file_seen
                    total_errors += errors
                    
                    # Update progress (batch update to database)
                    if total_written % progress_interval == 0:
                        scan_run_dal.update_scan_run(
                            scan_run_id=scan_run_id,
                            files_processed=total_written,
                            new_files=total_new_files,
                            changed_files=total_changed_files,
                            unchanged_files=total_unchanged_files,
                        )
                        # Use progress tracker if available (shows ETA and rate)
                        if progress_tracker:
                            progress_tracker.update(total_written)
                        else:
                            logger.info(
                                f"Progress: {{'files_processed': {total_written}, 'errors': {total_errors}}}"
                            )
                    
                    batch.clear()
                
                # Mark task as done
                results_queue.task_done()
                
            except Empty:
                # Queue is empty, check if we should flush partial batch
                if batch and shutdown_event.is_set():
                    _write_batch(batch, media_dal, error_dal, conn)
                    new_items = len([r for r in batch if r["type"] == "media_item" and not r.get("is_changed", False)])
                    changed_items = len([r for r in batch if r["type"] == "media_item" and r.get("is_changed", False)])
                    unchanged_items = len([r for r in batch if r["type"] == "file_seen"])
                    total_new_files += new_items
                    total_changed_files += changed_items
                    total_unchanged_files += unchanged_items
                    total_written += new_items + changed_items + unchanged_items
                    total_errors += len([r for r in batch if r["type"] == "error"])
                    batch.clear()
                continue
        
        # Flush any remaining items
        if batch:
            _write_batch(batch, media_dal, error_dal, conn)
            new_items = len([r for r in batch if r["type"] == "media_item" and not r.get("is_changed", False)])
            changed_items = len([r for r in batch if r["type"] == "media_item" and r.get("is_changed", False)])
            unchanged_items = len([r for r in batch if r["type"] == "file_seen"])
            total_new_files += new_items
            total_changed_files += changed_items
            total_unchanged_files += unchanged_items
            total_written += new_items + changed_items + unchanged_items
            total_errors += len([r for r in batch if r["type"] == "error"])
        
        # Final progress update with all statistics
        scan_run_dal.update_scan_run(
            scan_run_id=scan_run_id,
            files_processed=total_written,
            new_files=total_new_files,
            changed_files=total_changed_files,
            unchanged_files=total_unchanged_files,
            error_files=total_errors,
        )
        
    except Exception as e:
        logger.error(f"Writer thread crashed: {{'error': {str(e)!r}}}", exc_info=True)
        raise
    
    finally:
        conn.close()
        logger.info(
            f"Writer thread shutting down: {{'written': {total_written}, 'errors': {total_errors}}}"
        )


def _write_batch(
    batch: list,
    media_dal: MediaItemDAL,
    error_dal: ProcessingErrorDAL,
    conn: Any,
) -> None:
    """Write a batch of results to database.
    
    Args:
        batch: List of result dicts (media items, errors, or file_seen updates)
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
        # Collect file_seen updates for batch processing
        file_seen_updates = []
        
        for result in batch:
            if result["type"] == "media_item":
                # Insert or update media item (no commit - we batch commit at the end)
                record = result["record"]
                is_changed = result.get("is_changed", False)
                
                if is_changed:
                    # File exists but changed - update it
                    # Use INSERT OR REPLACE to update all fields
                    try:
                        # Delete old record and insert new one (simpler than updating all fields)
                        conn.execute("DELETE FROM media_items WHERE relative_path = ?", (record.relative_path,))
                        media_dal.insert_media_item(record)
                    except Exception as e:
                        logger.error(f"Failed to update changed file: {{'path': {record.relative_path!r}, 'error': {str(e)!r}}}")
                        raise
                else:
                    # New file - insert it
                    try:
                        media_dal.insert_media_item(record)
                    except sqlite3.IntegrityError as e:
                        # Handle duplicate path gracefully - log and skip
                        if "UNIQUE constraint failed: media_items.relative_path" in str(e):
                            logger.warning(
                                f"Skipping duplicate path: {{'path': {record.relative_path!r}, 'media_item_id': {record.media_item_id!r}}}"
                            )
                        else:
                            # Other integrity errors should still fail
                            raise
                
            elif result["type"] == "file_seen":
                # Collect for batch update
                file_seen_updates.append((
                    result["relative_path"],
                    result["scan_run_id"],
                    result["last_seen_timestamp"]
                ))
                
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
                logger.warning(f"Unknown result type: {{'type': {result['type']!r}}}")
        
        # Batch update file_seen records
        if file_seen_updates:
            rows_updated = media_dal.batch_update_files_seen(file_seen_updates)
            logger.debug(f"Batch updated {rows_updated} unchanged files")
        
        # Commit transaction
        conn.commit()
        
    except Exception as e:
        # Rollback on error
        conn.rollback()
        logger.error(f"Failed to write batch: {{'items': {len(batch)}, 'error': {str(e)!r}}}", exc_info=True)
        # Log first item for debugging (without full object dump)
        if batch:
            first_item = batch[0]
            logger.error(f"First item in failed batch: {{'type': {first_item.get('type')!r}, 'path': {first_item.get('relative_path', 'N/A')!r}}}")
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
    logger.info(f"Started writer thread with retry: {{'batch_size': {batch_size}, 'max_retries': {max_retries}}}")
    
    from pathlib import Path
    db_conn = DatabaseConnection(Path(db_path))
    conn = db_conn.connect()
    
    media_dal = MediaItemDAL(conn)
    error_dal = ProcessingErrorDAL(conn)
    scan_run_dal = ScanRunDAL(conn)
    
    total_written = 0
    total_errors = 0
    total_new_files = 0
    total_unchanged_files = 0
    total_changed_files = 0
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
                        new_items = len([r for r in batch if r["type"] == "media_item" and not r.get("is_changed", False)])
                        changed_items = len([r for r in batch if r["type"] == "media_item" and r.get("is_changed", False)])
                        unchanged_items = len([r for r in batch if r["type"] == "file_seen"])
                        total_new_files += new_items
                        total_changed_files += changed_items
                        total_unchanged_files += unchanged_items
                        total_written += new_items + changed_items + unchanged_items
                        total_errors += len([r for r in batch if r["type"] == "error"])
                    break
                
                batch.append(result)
                
                if len(batch) >= batch_size:
                    _write_batch_with_retry(
                        batch, media_dal, error_dal, conn, max_retries
                    )
                    
                    media_items = len([r for r in batch if r["type"] == "media_item"])
                    file_seen = len([r for r in batch if r["type"] == "file_seen"])
                    errors = len([r for r in batch if r["type"] == "error"])
                    total_new_files += media_items
                    total_unchanged_files += file_seen
                    total_written += media_items + file_seen
                    total_errors += errors
                    
                    if total_written % progress_interval == 0:
                        scan_run_dal.update_scan_run(
                            scan_run_id=scan_run_id,
                            files_processed=total_written,
                            new_files=total_new_files,
                            unchanged_files=total_unchanged_files,
                        )
                        logger.info(
                            f"Progress: {{'files_processed': {total_written}, 'errors': {total_errors}}}"
                        )
                    
                    batch.clear()
                
                results_queue.task_done()
                
            except Empty:
                if batch and shutdown_event.is_set():
                    _write_batch_with_retry(
                        batch, media_dal, error_dal, conn, max_retries
                    )
                    new_items = len([r for r in batch if r["type"] == "media_item" and not r.get("is_changed", False)])
                    changed_items = len([r for r in batch if r["type"] == "media_item" and r.get("is_changed", False)])
                    unchanged_items = len([r for r in batch if r["type"] == "file_seen"])
                    total_new_files += new_items
                    total_changed_files += changed_items
                    total_unchanged_files += unchanged_items
                    total_written += new_items + changed_items + unchanged_items
                    total_errors += len([r for r in batch if r["type"] == "error"])
                    batch.clear()
                continue
        
        if batch:
            _write_batch_with_retry(
                batch, media_dal, error_dal, conn, max_retries
            )
            new_items = len([r for r in batch if r["type"] == "media_item" and not r.get("is_changed", False)])
            changed_items = len([r for r in batch if r["type"] == "media_item" and r.get("is_changed", False)])
            unchanged_items = len([r for r in batch if r["type"] == "file_seen"])
            total_new_files += new_items
            total_changed_files += changed_items
            total_unchanged_files += unchanged_items
            total_written += new_items + changed_items + unchanged_items
            total_errors += len([r for r in batch if r["type"] == "error"])
        
        scan_run_dal.update_scan_run(
            scan_run_id=scan_run_id,
            files_processed=total_written,
            new_files=total_new_files,
            changed_files=total_changed_files,
            unchanged_files=total_unchanged_files,
            error_files=total_errors,
        )
        
    except Exception as e:
        logger.error(f"Writer thread crashed: {{'error': {str(e)!r}}}", exc_info=True)
        raise
    
    finally:
        conn.close()
        logger.info(
            f"Writer thread shutting down: {{'written': {total_written}, 'errors': {total_errors}}}"
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
                    f"Batch write failed: {{'attempt': {attempt + 1}, 'max_retries': {max_retries}, 'retry_in_seconds': {wait_time}, 'error': {str(e)!r}}}"
                )
                time.sleep(wait_time)
            else:
                # Final attempt failed
                logger.error(f"Batch write failed after retries: {{'max_retries': {max_retries}, 'error': {str(e)!r}}}")
                raise
