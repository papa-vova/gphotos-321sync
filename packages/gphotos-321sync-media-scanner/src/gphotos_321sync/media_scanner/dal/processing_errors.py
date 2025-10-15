"""Data Access Layer for processing_errors table."""

import logging
from typing import List, Dict, Any

from ..database import DatabaseConnection

logger = logging.getLogger(__name__)


class ProcessingErrorDAL:
    """
    Data access layer for processing_errors table.
    
    Records errors encountered during scanning.
    """
    
    def __init__(self, db: DatabaseConnection):
        """
        Initialize processing error DAL.
        
        Args:
            db: Database connection
        """
        self.db = db
    
    def insert_error(
        self,
        scan_run_id: str,
        relative_path: str,
        error_type: str,
        error_category: str,
        error_message: str
    ):
        """
        Insert a processing error.
        
        Args:
            scan_run_id: Scan run ID
            relative_path: Path to file that failed
            error_type: Type of error ('media_file', 'json_sidecar', 'album_metadata')
            error_category: Category ('permission_denied', 'corrupted', 'io_error', 'parse_error', 'unsupported_format')
            error_message: Detailed error message
        """
        cursor = self.db.execute(
            """
            INSERT INTO processing_errors (
                scan_run_id, relative_path, error_type,
                error_category, error_message
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (scan_run_id, relative_path, error_type, error_category, error_message)
        )
        cursor.close()
        
        logger.debug(f"Recorded error for {relative_path}: {error_category}")
    
    def get_errors_by_scan(self, scan_run_id: str) -> List[Dict[str, Any]]:
        """
        Get all errors for a scan run.
        
        Args:
            scan_run_id: Scan run ID
            
        Returns:
            List of error dictionaries
        """
        cursor = self.db.execute(
            """
            SELECT * FROM processing_errors
            WHERE scan_run_id = ?
            ORDER BY timestamp
            """,
            (scan_run_id,)
        )
        rows = cursor.fetchall()
        cursor.close()
        
        return [dict(row) for row in rows]
    
    def get_errors_by_path(self, relative_path: str) -> List[Dict[str, Any]]:
        """
        Get all errors for a specific file path.
        
        Args:
            relative_path: File path
            
        Returns:
            List of error dictionaries
        """
        cursor = self.db.execute(
            """
            SELECT * FROM processing_errors
            WHERE relative_path = ?
            ORDER BY timestamp DESC
            """,
            (relative_path,)
        )
        rows = cursor.fetchall()
        cursor.close()
        
        return [dict(row) for row in rows]
    
    def get_error_summary(self, scan_run_id: str) -> Dict[str, int]:
        """
        Get error summary statistics for a scan run.
        
        Args:
            scan_run_id: Scan run ID
            
        Returns:
            Dictionary with error counts by category
        """
        cursor = self.db.execute(
            """
            SELECT error_category, COUNT(*) as count
            FROM processing_errors
            WHERE scan_run_id = ?
            GROUP BY error_category
            """,
            (scan_run_id,)
        )
        rows = cursor.fetchall()
        cursor.close()
        
        return {row['error_category']: row['count'] for row in rows}
    
    def get_error_count(self, scan_run_id: str) -> int:
        """
        Get total error count for a scan run.
        
        Args:
            scan_run_id: Scan run ID
            
        Returns:
            Total number of errors
        """
        cursor = self.db.execute(
            """
            SELECT COUNT(*) as count
            FROM processing_errors
            WHERE scan_run_id = ?
            """,
            (scan_run_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        
        return row['count'] if row else 0
    
    def batch_insert_errors(self, errors: List[Dict[str, Any]]) -> int:
        """
        Insert multiple errors in a batch.
        
        Args:
            errors: List of error dictionaries with keys:
                scan_run_id, relative_path, error_type, error_category, error_message
                
        Returns:
            Number of errors inserted
        """
        if not errors:
            return 0
        
        data = [
            (
                error['scan_run_id'],
                error['relative_path'],
                error['error_type'],
                error['error_category'],
                error['error_message']
            )
            for error in errors
        ]
        
        cursor = self.db.executemany(
            """
            INSERT INTO processing_errors (
                scan_run_id, relative_path, error_type,
                error_category, error_message
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            data
        )
        count = cursor.rowcount
        cursor.close()
        
        logger.debug(f"Batch inserted {count} errors")
        return count
