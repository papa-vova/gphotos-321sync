"""Post-scan validation and cleanup."""

import logging
from datetime import datetime
from typing import Dict, Any

from .database import DatabaseConnection

logger = logging.getLogger(__name__)


def validate_scan(db_path: str, scan_run_id: str, scan_start_time: datetime) -> Dict[str, Any]:
    """
    Perform post-scan validation to detect inconsistencies and missing files.
    
    This function:
    1. Marks files as 'inconsistent' if they have current scan_run_id but old timestamp
    2. Marks files as 'missing' if they have old scan_run_id and status='present'
    3. Verifies all present files have current scan_run_id
    4. Returns validation statistics
    
    Args:
        db_path: Path to database (string or Path)
        scan_run_id: Current scan run ID
        scan_start_time: When the scan started
        
    Returns:
        Dictionary with validation statistics
    """
    from pathlib import Path
    
    logger.info(f"Starting post-scan validation for scan_run {scan_run_id}")
    
    db_conn = DatabaseConnection(Path(db_path) if isinstance(db_path, str) else db_path)
    conn = db_conn.connect()
    
    try:
        # Step 1: Mark inconsistent files
        # Files from PREVIOUS scans that have old timestamps
        # Get the current scan's start time from the database
        cursor = conn.execute(
            "SELECT start_timestamp FROM scan_runs WHERE scan_run_id = ?",
            (scan_run_id,)
        )
        row = cursor.fetchone()
        if row:
            db_scan_start = row[0]
            cursor.close()
            
            # Mark files from previous scans with timestamps before this scan started
            cursor = conn.execute(
                """
                UPDATE media_items
                SET status = 'inconsistent'
                WHERE scan_run_id != ?
                  AND last_seen_timestamp < ?
                  AND status = 'present'
                """,
                (scan_run_id, db_scan_start)
            )
            inconsistent_count = cursor.rowcount
            cursor.close()
        else:
            inconsistent_count = 0
            cursor.close()
        
        # Step 2: Mark missing files
        # Files that were 'present' but weren't seen in this scan
        # (have old scan_run_id and status='present')
        cursor = conn.execute(
            """
            UPDATE media_items
            SET status = 'missing'
            WHERE scan_run_id != ?
              AND status = 'present'
            """,
            (scan_run_id,)
        )
        missing_count = cursor.rowcount
        cursor.close()
        
        if missing_count > 0:
            logger.info(f"Marked {missing_count} media_item(s) as missing")
        
        # Step 3: Mark missing albums
        cursor = conn.execute(
            """
            UPDATE albums
            SET status = 'missing'
            WHERE scan_run_id != ?
              AND status = 'present'
            """,
            (scan_run_id,)
        )
        missing_albums_count = cursor.rowcount
        cursor.close()
        
        if missing_albums_count > 0:
            logger.info(f"Marked {missing_albums_count} album(s) as missing")
        
        # Step 4: Update scan_runs statistics
        cursor = conn.execute(
            """
            UPDATE scan_runs
            SET inconsistent_files = ?,
                missing_files = ?
            WHERE scan_run_id = ?
            """,
            (inconsistent_count, missing_count, scan_run_id)
        )
        cursor.close()
        
        # Step 5: Verify present files have current scan_run_id
        cursor = conn.execute(
            """
            SELECT COUNT(*) FROM media_items
            WHERE status = 'present'
              AND scan_run_id != ?
            """,
            (scan_run_id,)
        )
        orphaned_present_count = cursor.fetchone()[0]
        cursor.close()
        
        if orphaned_present_count > 0:
            logger.error(
                f"Found orphaned files: {{'count': {orphaned_present_count}, 'status': 'present', 'issue': 'wrong scan_run_id'}}"
            )
        
        # Step 6: Get validation summary
        cursor = conn.execute(
            """
            SELECT 
                COUNT(*) as total_files,
                SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present_files,
                SUM(CASE WHEN status = 'missing' THEN 1 ELSE 0 END) as missing_files,
                SUM(CASE WHEN status = 'inconsistent' THEN 1 ELSE 0 END) as inconsistent_files,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_files
            FROM media_items
            """
        )
        row = cursor.fetchone()
        cursor.close()
        
        conn.commit()
        
        validation_stats = {
            'scan_run_id': scan_run_id,
            'total_files': row[0] or 0,
            'present_files': row[1] or 0,
            'missing_files': row[2] or 0,
            'inconsistent_files': row[3] or 0,
            'error_files': row[4] or 0,
            'orphaned_present_files': orphaned_present_count,
            'missing_albums': missing_albums_count,
        }
        
        # Step 7: Validate scan_runs statistics against actual counts
        cursor = conn.execute(
            "SELECT * FROM scan_runs WHERE scan_run_id = ?",
            (scan_run_id,)
        )
        scan_run = cursor.fetchone()
        cursor.close()
        
        if scan_run:
            # Check files_processed vs actual media_items count
            cursor = conn.execute(
                "SELECT COUNT(*) FROM media_items WHERE scan_run_id = ?",
                (scan_run_id,)
            )
            actual_items_count = cursor.fetchone()[0]
            cursor.close()
            
            reported_processed = scan_run['files_processed']
            if reported_processed != actual_items_count:
                logger.warning(
                    f"Statistics mismatch: {{'scan_run_id': {scan_run_id!r}, "
                    f"'files_processed': {reported_processed}, 'actual_items': {actual_items_count}, "
                    f"'difference': {abs(reported_processed - actual_items_count)}}}"
                )
            
            # Check albums_total vs actual albums count
            cursor = conn.execute(
                "SELECT COUNT(*) FROM albums WHERE scan_run_id = ?",
                (scan_run_id,)
            )
            actual_albums_count = cursor.fetchone()[0]
            cursor.close()
            
            reported_albums = scan_run['albums_total']
            if reported_albums != actual_albums_count:
                logger.warning(
                    f"Albums mismatch: {{'scan_run_id': {scan_run_id!r}, "
                    f"'albums_total': {reported_albums}, 'actual_albums': {actual_albums_count}, "
                    f"'difference': {abs(reported_albums - actual_albums_count)}}}"
                )
            
            # Add validation results to stats
            validation_stats['statistics_validation'] = {
                'files_processed_reported': reported_processed,
                'files_processed_actual': actual_items_count,
                'albums_total_reported': reported_albums,
                'albums_total_actual': actual_albums_count,
            }
        
        logger.info(f"Completed post-scan validation: {validation_stats}")
        
        return validation_stats
        
    finally:
        conn.close()


def cleanup_old_scan_data(db_path: str, keep_recent_scans: int = 10) -> Dict[str, int]:
    """
    Clean up data from old scan runs to prevent database bloat.
    
    Keeps the most recent N scan runs and removes:
    - Old scan_runs records
    - Processing errors from old scans
    - Does NOT remove media_items or albums (they persist across scans)
    
    Args:
        db_path: Path to database (string or Path)
        keep_recent_scans: Number of recent scan runs to keep (default: 10)
        
    Returns:
        Dictionary with cleanup statistics
    """
    from pathlib import Path
    
    logger.info(f"Starting cleanup: {{'keep_recent_scans': {keep_recent_scans}}}")
    
    db_conn = DatabaseConnection(Path(db_path) if isinstance(db_path, str) else db_path)
    conn = db_conn.connect()
    
    try:
        # Get scan_run_ids to delete (all except the most recent N)
        cursor = conn.execute(
            """
            SELECT scan_run_id
            FROM scan_runs
            ORDER BY start_timestamp DESC
            LIMIT -1 OFFSET ?
            """,
            (keep_recent_scans,)
        )
        old_scan_ids = [row[0] for row in cursor.fetchall()]
        cursor.close()
        
        if not old_scan_ids:
            logger.info("No old scan_runs to clean up")
            return {
                'scan_runs_deleted': 0,
                'errors_deleted': 0,
            }
        
        # Delete processing errors from old scans
        placeholders = ','.join('?' * len(old_scan_ids))
        cursor = conn.execute(
            f"""
            DELETE FROM processing_errors
            WHERE scan_run_id IN ({placeholders})
            """,
            old_scan_ids
        )
        errors_deleted = cursor.rowcount
        cursor.close()
        
        # Delete old scan_runs
        cursor = conn.execute(
            f"""
            DELETE FROM scan_runs
            WHERE scan_run_id IN ({placeholders})
            """,
            old_scan_ids
        )
        scans_deleted = cursor.rowcount
        cursor.close()
        
        conn.commit()
        
        cleanup_stats = {
            'scan_runs_deleted': scans_deleted,
            'errors_deleted': errors_deleted,
        }
        
        logger.info(f"Completed cleanup: {cleanup_stats}")
        
        return cleanup_stats
        
    finally:
        conn.close()
