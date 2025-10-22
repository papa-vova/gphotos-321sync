"""Data Access Layer for scan_runs table."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from ..database import DatabaseConnection

logger = logging.getLogger(__name__)


class ScanRunDAL:
    """
    Data access layer for scan_runs table.
    
    Manages scan run lifecycle and statistics.
    """
    
    def __init__(self, db: DatabaseConnection):
        """
        Initialize scan run DAL.
        
        Args:
            db: Database connection
        """
        self.db = db
    
    def create_scan_run(self) -> str:
        """
        Create a new scan run with explicit UTC timestamp.
        
        Returns:
            scan_run_id (UUID4 string)
        """
        scan_run_id = str(uuid.uuid4())
        start_timestamp = datetime.now(timezone.utc).isoformat()
        
        cursor = self.db.execute(
            """
            INSERT INTO scan_runs (scan_run_id, status, start_timestamp)
            VALUES (?, 'running', ?)
            """,
            (scan_run_id, start_timestamp)
        )
        cursor.close()
        self.db.commit()
        
        logger.info(f"Created scan_run {scan_run_id}")
        return scan_run_id
    
    def update_scan_run(self, scan_run_id: str, **fields):
        """
        Update scan run fields.
        
        Args:
            scan_run_id: Scan run ID
            **fields: Fields to update (e.g., media_files_processed=100)
        """
        if not fields:
            return
        
        # Build SET clause
        set_clause = ", ".join(f"{key} = ?" for key in fields.keys())
        values = list(fields.values())
        values.append(scan_run_id)
        
        cursor = self.db.execute(
            f"UPDATE scan_runs SET {set_clause} WHERE scan_run_id = ?",
            values
        )
        cursor.close()
        self.db.commit()
        
        logger.debug(f"Updated scan_run {scan_run_id}: {list(fields.keys())}")
    
    def complete_scan_run(self, scan_run_id: str, status: str = 'completed'):
        """
        Mark scan run as completed or failed with explicit UTC timestamp.
        
        Args:
            scan_run_id: Scan run ID
            status: Final status ('completed' or 'failed')
        """
        end_timestamp = datetime.now(timezone.utc).isoformat()
        
        cursor = self.db.execute(
            """
            UPDATE scan_runs
            SET status = ?,
                end_timestamp = ?,
                duration_seconds = (
                    julianday(?) - julianday(start_timestamp)
                ) * 86400,
                files_per_second = CASE
                    WHEN media_files_processed > 0 THEN
                        CAST(media_files_processed AS REAL) / 
                        ((julianday(?) - julianday(start_timestamp)) * 86400)
                    ELSE 0
                END
            WHERE scan_run_id = ?
            """,
            (status, end_timestamp, end_timestamp, end_timestamp, scan_run_id)
        )
        cursor.close()
        self.db.commit()
        
        logger.info(f"Completed scan_run {scan_run_id}: {{'status': {status!r}}}")
    
    def get_scan_run(self, scan_run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get scan run by ID.
        
        Args:
            scan_run_id: Scan run ID
            
        Returns:
            Dictionary with scan run data, or None if not found
        """
        cursor = self.db.execute(
            "SELECT * FROM scan_runs WHERE scan_run_id = ?",
            (scan_run_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return dict(row)
        return None
    
    def get_latest_scan_run(self) -> Optional[Dict[str, Any]]:
        """
        Get the most recent scan run.
        
        Returns:
            Dictionary with scan run data, or None if no runs exist
        """
        cursor = self.db.execute(
            """
            SELECT * FROM scan_runs
            ORDER BY start_timestamp DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return dict(row)
        return None
    
    def increment_counter(self, scan_run_id: str, counter_name: str, increment: int = 1):
        """
        Increment a counter field in scan_runs.
        
        Args:
            scan_run_id: Scan run ID
            counter_name: Name of counter field (e.g., 'media_files_processed')
            increment: Amount to increment by (default: 1)
        """
        cursor = self.db.execute(
            f"""
            UPDATE scan_runs
            SET {counter_name} = {counter_name} + ?
            WHERE scan_run_id = ?
            """,
            (increment, scan_run_id)
        )
        cursor.close()
        # Note: Don't commit here - let batch writer handle commits
    
    def get_scan_statistics(self, scan_run_id: str) -> Dict[str, Any]:
        """
        Get statistics for a scan run.
        
        Args:
            scan_run_id: Scan run ID
            
        Returns:
            Dictionary with statistics
        """
        scan_run = self.get_scan_run(scan_run_id)
        if not scan_run:
            return {}
        
        return {
            'scan_run_id': scan_run_id,
            'status': scan_run['status'],
            'duration_seconds': scan_run['duration_seconds'],
            'files_per_second': scan_run['files_per_second'],
            'total_files_discovered': scan_run['total_files_discovered'],
            'media_files_discovered': scan_run['media_files_discovered'],
            'metadata_files_discovered': scan_run['metadata_files_discovered'],
            'media_files_processed': scan_run['media_files_processed'],
            'metadata_files_processed': scan_run['metadata_files_processed'],
            'media_new_files': scan_run['media_new_files'],
            'media_unchanged_files': scan_run['media_unchanged_files'],
            'media_changed_files': scan_run['media_changed_files'],
            'missing_files': scan_run['missing_files'],
            'media_error_files': scan_run['media_error_files'],
            'inconsistent_files': scan_run['inconsistent_files'],
            'albums_total': scan_run['albums_total'],
        }
