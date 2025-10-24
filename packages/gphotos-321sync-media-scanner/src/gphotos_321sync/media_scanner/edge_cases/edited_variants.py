"""Edited variant detection and linking.

Google Photos creates edited variants with a '-edited' suffix.
For example: IMG_1234.JPG (original) and IMG_1234-edited.JPG (edited version).
"""

import logging
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

from gphotos_321sync.common.path_utils import normalize_path

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """Information about a file for edited variant detection."""
    relative_path: str
    media_item_id: Optional[str] = None
    mime_type: Optional[str] = None


def detect_edited_variants(files: List[FileInfo]) -> Dict[str, str]:
    """
    Detect edited variants and map them to their originals.
    
    Edited variants are identified by:
    1. Filename contains '-edited' suffix before extension
    2. Original file exists with same name minus '-edited'
    3. Both files in same directory
    4. Same file extension
    
    Args:
        files: List of FileInfo objects to analyze
        
    Returns:
        Dictionary mapping edited_path -> original_path
    """
    logger.info(f"Detecting edited variants: {{'files': {len(files)}}}")
    
    # Build a map of normalized paths to original paths for lookup
    normalized_to_original = {normalize_path(f.relative_path): f.relative_path for f in files}
    
    # Map to store edited -> original relationships (using original DB paths)
    edited_to_original: Dict[str, str] = {}
    
    for file_info in files:
        path = Path(file_info.relative_path)
        stem = path.stem  # Filename without extension
        
        # Check if this is an edited variant
        if '-edited' not in stem:
            continue
        
        # Construct the original filename (normalized for comparison)
        # Only remove the LAST occurrence of '-edited' to handle multiple edits
        if stem.endswith('-edited'):
            original_stem = stem[:-7]  # Remove '-edited' suffix
        else:
            # Handle case where -edited is in the middle (shouldn't happen but be safe)
            original_stem = stem.rsplit('-edited', 1)[0]
        original_path_normalized = normalize_path(path.parent / f"{original_stem}{path.suffix}")
        
        # Check if original exists (using normalized paths for comparison)
        if original_path_normalized in normalized_to_original:
            # Store using original DB paths (not normalized)
            original_path_db = normalized_to_original[original_path_normalized]
            edited_to_original[file_info.relative_path] = original_path_db
            logger.debug(
                f"Detected edited variant: {{'edited': {file_info.relative_path!r}, 'original': {original_path_db!r}}}"
            )
    
    logger.info(f"Detected edited variants: {{'count': {len(edited_to_original)}}}")
    
    return edited_to_original


def link_edited_variants(
    db_conn: sqlite3.Connection,
    edited_to_original: Dict[str, str]
) -> Dict[str, int]:
    """
    Link edited variants to their originals in the database.
    
    Sets the original_media_item_id field on edited variants to point to
    the media_item_id of the original file.
    
    Args:
        db_conn: Database connection
        edited_to_original: Dictionary mapping edited_path -> original_path
        
    Returns:
        Dictionary with statistics (variants_linked, originals_found, originals_missing)
    """
    logger.info(f"Linking edited variants: {{'count': {len(edited_to_original)}}}")
    
    variants_linked = 0
    originals_found = 0
    originals_missing = 0
    
    for edited_path, original_path in edited_to_original.items():
        logger.debug(f"Processing pair: {{'edited': {edited_path!r}, 'original': {original_path!r}}}")
        
        # Get the original's media_item_id
        cursor = db_conn.execute(
            """
            SELECT media_item_id
            FROM media_items
            WHERE relative_path = ?
            """,
            (original_path,)
        )
        row = cursor.fetchone()
        cursor.close()
        
        if not row:
            logger.warning(
                f"Original not found for edited variant: {{'edited': {edited_path!r}, 'original': {original_path!r}}}"
            )
            originals_missing += 1
            continue
        
        original_media_item_id = row[0]
        originals_found += 1
        
        # Update the edited variant with the original's ID
        cursor = db_conn.execute(
            """
            UPDATE media_items
            SET original_media_item_id = ?
            WHERE relative_path = ?
            """,
            (original_media_item_id, edited_path)
        )
        
        if cursor.rowcount > 0:
            variants_linked += 1
            logger.debug(
                f"Linked edited variant: {{'edited': {edited_path!r}, 'original_id': {original_media_item_id!r}}}"
            )
        else:
            logger.warning(
                f"Failed to update edited variant: {{'path': {edited_path!r}}}"
            )
        
        cursor.close()
    
    db_conn.commit()
    
    stats = {
        'variants_linked': variants_linked,
        'originals_found': originals_found,
        'originals_missing': originals_missing,
    }
    
    logger.info(f"Edited variant linking completed: {stats}")
    
    return stats


def detect_and_link_edited_variants(db_path: str, scan_run_id: str) -> Dict[str, int]:
    """
    Detect and link edited variants for a scan run.
    
    This is a convenience function that:
    1. Queries all media items from the scan run
    2. Detects edited variants
    3. Links them to originals in the database
    
    Args:
        db_path: Path to database (string or Path)
        scan_run_id: Scan run ID to process
        
    Returns:
        Dictionary with statistics
    """
    from pathlib import Path
    from ..database import DatabaseConnection
    
    logger.info(f"Processing edited variants for scan_run {scan_run_id}")
    
    db_conn = DatabaseConnection(Path(db_path))
    conn = db_conn.connect()
    
    try:
        # Get all media items from this scan run
        logger.info(f"Querying media items for scan_run {scan_run_id}")
        cursor = conn.execute(
            """
            SELECT media_item_id, relative_path, mime_type
            FROM media_items
            WHERE scan_run_id = ?
              AND status = 'present'
            """,
            (scan_run_id,)
        )
        
        files = []
        for row in cursor.fetchall():
            files.append(FileInfo(
                media_item_id=row[0],
                relative_path=row[1],
                mime_type=row[2],
            ))
        
        cursor.close()
        logger.info(f"Query returned files: {{'count': {len(files)}}}")
        
        # Detect edited variants
        logger.info(f"Detecting edited variants: {{'files': {len(files)}}}")
        edited_to_original = detect_edited_variants(files)
        logger.info(f"Detection found edited variants: {{'count': {len(edited_to_original)}}}")
        
        # Link variants
        if edited_to_original:
            logger.info(f"Linking variants: {{'count': {len(edited_to_original)}}}")
            stats = link_edited_variants(conn, edited_to_original)
        else:
            logger.info("No edited variants detected")
            stats = {
                'variants_linked': 0,
                'originals_found': 0,
                'originals_missing': 0,
            }
        
        conn.commit()
        return stats
        
    finally:
        conn.close()
