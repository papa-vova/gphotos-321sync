"""Scan summary report generation."""

import logging
from typing import Dict, Any, List
from datetime import datetime

from .database import DatabaseConnection
from .dal.scan_runs import ScanRunDAL

logger = logging.getLogger(__name__)


def generate_summary(db_path: str, scan_run_id: str) -> Dict[str, Any]:
    """
    Generate a comprehensive summary report for a scan run.
    
    Includes:
    - Scan run metadata (timestamps, duration, status)
    - File statistics (discovered, processed, new, changed, etc.)
    - Album statistics
    - Error breakdown by type and category
    - Performance metrics
    
    Args:
        db_path: Path to database (string or Path)
        scan_run_id: Scan run ID to summarize
        
    Returns:
        Dictionary with complete scan summary
    """
    from pathlib import Path
    
    logger.info(f"Generating summary for scan_run_id: {scan_run_id}")
    
    db_conn = DatabaseConnection(Path(db_path) if isinstance(db_path, str) else db_path)
    conn = db_conn.connect()
    
    try:
        scan_run_dal = ScanRunDAL(conn)
        
        # Get scan run data
        scan_run = scan_run_dal.get_scan_run(scan_run_id)
        if not scan_run:
            raise ValueError(f"Scan run not found: {scan_run_id}")
        
        # Get error breakdown
        error_breakdown = _get_error_breakdown(conn, scan_run_id)
        
        # Get file status breakdown
        file_status = _get_file_status_breakdown(conn)
        
        # Get album statistics
        album_stats = _get_album_statistics(conn, scan_run_id)
        
        # Build summary
        summary = {
            'scan_run_id': scan_run_id,
            'status': scan_run['status'],
            'timestamps': {
                'start': scan_run['start_timestamp'],
                'end': scan_run['end_timestamp'],
                'duration_seconds': scan_run['duration_seconds'],
            },
            'discovery': {
                'total_files_discovered': scan_run['total_files_discovered'],
                'media_files_discovered': scan_run['media_files_discovered'],
                'metadata_files_discovered': scan_run['metadata_files_discovered'],
            },
            'processing': {
                'files_processed': scan_run['files_processed'],
                'new_files': scan_run['new_files'],
                'unchanged_files': scan_run['unchanged_files'],
                'changed_files': scan_run['changed_files'],
                'missing_files': scan_run['missing_files'],
                'error_files': scan_run['error_files'],
                'inconsistent_files': scan_run['inconsistent_files'],
            },
            'albums': {
                'total': scan_run['albums_total'],
                'files_in_albums': scan_run['files_in_albums'],
                'present': album_stats['present'],
                'missing': album_stats['missing'],
                'error': album_stats['error'],
            },
            'file_status': file_status,
            'errors': error_breakdown,
            'performance': {
                'duration_seconds': scan_run['duration_seconds'],
                'files_per_second': scan_run['files_per_second'],
            },
        }
        
        logger.info(f"Summary generated successfully for scan_run_id: {scan_run_id}")
        
        return summary
        
    finally:
        conn.close()


def _get_error_breakdown(conn, scan_run_id: str) -> Dict[str, Any]:
    """Get error breakdown by type and category."""
    cursor = conn.execute(
        """
        SELECT 
            error_type,
            error_category,
            COUNT(*) as count
        FROM processing_errors
        WHERE scan_run_id = ?
        GROUP BY error_type, error_category
        ORDER BY count DESC
        """,
        (scan_run_id,)
    )
    
    errors_by_type_category = []
    total_errors = 0
    
    for row in cursor.fetchall():
        errors_by_type_category.append({
            'error_type': row[0],
            'error_category': row[1],
            'count': row[2],
        })
        total_errors += row[2]
    
    cursor.close()
    
    # Get error type totals
    cursor = conn.execute(
        """
        SELECT 
            error_type,
            COUNT(*) as count
        FROM processing_errors
        WHERE scan_run_id = ?
        GROUP BY error_type
        ORDER BY count DESC
        """,
        (scan_run_id,)
    )
    
    errors_by_type = {row[0]: row[1] for row in cursor.fetchall()}
    cursor.close()
    
    # Get error category totals
    cursor = conn.execute(
        """
        SELECT 
            error_category,
            COUNT(*) as count
        FROM processing_errors
        WHERE scan_run_id = ?
        GROUP BY error_category
        ORDER BY count DESC
        """,
        (scan_run_id,)
    )
    
    errors_by_category = {row[0]: row[1] for row in cursor.fetchall()}
    cursor.close()
    
    return {
        'total': total_errors,
        'by_type': errors_by_type,
        'by_category': errors_by_category,
        'by_type_and_category': errors_by_type_category,
    }


def _get_file_status_breakdown(conn) -> Dict[str, int]:
    """Get current file status breakdown across all files."""
    cursor = conn.execute(
        """
        SELECT 
            status,
            COUNT(*) as count
        FROM media_items
        GROUP BY status
        """
    )
    
    status_breakdown = {row[0]: row[1] for row in cursor.fetchall()}
    cursor.close()
    
    return status_breakdown


def _get_album_statistics(conn, scan_run_id: str) -> Dict[str, int]:
    """Get album statistics."""
    cursor = conn.execute(
        """
        SELECT 
            status,
            COUNT(*) as count
        FROM albums
        GROUP BY status
        """
    )
    
    album_stats = {
        'present': 0,
        'missing': 0,
        'error': 0,
    }
    
    for row in cursor.fetchall():
        album_stats[row[0]] = row[1]
    
    cursor.close()
    
    return album_stats


def format_summary_human_readable(summary: Dict[str, Any]) -> str:
    """
    Format summary as human-readable text.
    
    Args:
        summary: Summary dictionary from generate_summary()
        
    Returns:
        Formatted text report
    """
    lines = []
    
    lines.append("=" * 70)
    lines.append("SCAN SUMMARY REPORT")
    lines.append("=" * 70)
    lines.append("")
    
    # Basic info
    lines.append(f"Scan Run ID: {summary['scan_run_id']}")
    lines.append(f"Status: {summary['status'].upper()}")
    lines.append("")
    
    # Timestamps
    lines.append("TIMING")
    lines.append("-" * 70)
    lines.append(f"Started:  {summary['timestamps']['start']}")
    lines.append(f"Ended:    {summary['timestamps']['end']}")
    duration = summary['timestamps']['duration_seconds']
    if duration:
        lines.append(f"Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
    lines.append("")
    
    # Discovery
    lines.append("DISCOVERY")
    lines.append("-" * 70)
    disc = summary['discovery']
    lines.append(f"Total files discovered:    {disc['total_files_discovered']:>8,}")
    lines.append(f"Media files discovered:    {disc['media_files_discovered']:>8,}")
    lines.append(f"Metadata files discovered: {disc['metadata_files_discovered']:>8,}")
    lines.append("")
    
    # Processing
    lines.append("PROCESSING")
    lines.append("-" * 70)
    proc = summary['processing']
    lines.append(f"Files processed:     {proc['files_processed']:>8,}")
    lines.append(f"New files:           {proc['new_files']:>8,}")
    lines.append(f"Unchanged files:     {proc['unchanged_files']:>8,}")
    lines.append(f"Changed files:       {proc['changed_files']:>8,}")
    lines.append(f"Missing files:       {proc['missing_files']:>8,}")
    lines.append(f"Error files:         {proc['error_files']:>8,}")
    lines.append(f"Inconsistent files:  {proc['inconsistent_files']:>8,}")
    lines.append("")
    
    # Albums
    lines.append("ALBUMS")
    lines.append("-" * 70)
    albums = summary['albums']
    lines.append(f"Total albums:        {albums['total']:>8,}")
    lines.append(f"Files in albums:     {albums['files_in_albums']:>8,}")
    lines.append(f"Present albums:      {albums['present']:>8,}")
    lines.append(f"Missing albums:      {albums['missing']:>8,}")
    lines.append(f"Error albums:        {albums['error']:>8,}")
    lines.append("")
    
    # File status
    lines.append("FILE STATUS")
    lines.append("-" * 70)
    for status, count in sorted(summary['file_status'].items()):
        lines.append(f"{status.capitalize():20s} {count:>8,}")
    lines.append("")
    
    # Errors
    if summary['errors']['total'] > 0:
        lines.append("ERRORS")
        lines.append("-" * 70)
        lines.append(f"Total errors: {summary['errors']['total']:,}")
        lines.append("")
        
        lines.append("By Type:")
        for error_type, count in sorted(
            summary['errors']['by_type'].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            lines.append(f"  {error_type:20s} {count:>8,}")
        lines.append("")
        
        lines.append("By Category:")
        for category, count in sorted(
            summary['errors']['by_category'].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            lines.append(f"  {category:20s} {count:>8,}")
        lines.append("")
    
    # Performance
    lines.append("PERFORMANCE")
    lines.append("-" * 70)
    perf = summary['performance']
    if perf['duration_seconds']:
        lines.append(f"Duration:        {perf['duration_seconds']:.2f} seconds")
    if perf['files_per_second']:
        lines.append(f"Throughput:      {perf['files_per_second']:.2f} files/second")
    lines.append("")
    
    lines.append("=" * 70)
    
    return "\n".join(lines)
