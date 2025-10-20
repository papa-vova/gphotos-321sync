"""Live Photo detection and linking.

Apple Live Photos consist of a HEIC/JPG image and a MOV video with the same base filename.
For example: IMG_1234.HEIC and IMG_1234.MOV form a Live Photo pair.
"""

import logging
import uuid
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

from gphotos_321sync.common.path_utils import normalize_path

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """Information about a file for Live Photo detection."""
    relative_path: str
    media_item_id: Optional[str] = None
    mime_type: Optional[str] = None


def detect_live_photo_pairs(files: List[FileInfo]) -> List[Tuple[FileInfo, FileInfo]]:
    """
    Detect Live Photo pairs (HEIC/JPG + MOV with same base name).
    
    Live Photos are identified by:
    1. Same base filename (without extension)
    2. One file is HEIC or JPG (image)
    3. Other file is MOV (video)
    4. Both files in same directory
    
    Args:
        files: List of FileInfo objects to analyze
        
    Returns:
        List of (image_file, video_file) tuples representing Live Photo pairs
    """
    logger.info(f"Detecting Live Photo pairs: {{'files': {len(files)}}}")
    
    # Group files by directory and base name
    file_groups: Dict[Tuple[str, str], List[FileInfo]] = {}
    
    for file_info in files:
        path = Path(file_info.relative_path)
        directory = normalize_path(path.parent)
        base_name = path.stem  # Filename without extension
        extension = path.suffix.lower()
        
        # Only consider image and video files
        if extension not in ['.heic', '.jpg', '.jpeg', '.mov']:
            continue
        
        key = (directory, base_name)
        if key not in file_groups:
            file_groups[key] = []
        file_groups[key].append(file_info)
    
    # Find pairs
    pairs = []
    
    for (directory, base_name), group_files in file_groups.items():
        if len(group_files) < 2:
            continue
        
        # Separate into images and videos
        images = []
        videos = []
        
        for file_info in group_files:
            extension = Path(file_info.relative_path).suffix.lower()
            
            if extension in ['.heic', '.jpg', '.jpeg']:
                images.append(file_info)
            elif extension == '.mov':
                videos.append(file_info)
        
        # Match images with videos
        for image in images:
            for video in videos:
                pairs.append((image, video))
                logger.debug(
                    f"Detected Live Photo pair: {{'image': {image.relative_path!r}, 'video': {video.relative_path!r}}}"
                )
    
    logger.info(f"Detected Live Photo pairs: {{'count': {len(pairs)}}}")
    
    return pairs


def link_live_photo_pairs(
    db_conn,
    pairs: List[Tuple[FileInfo, FileInfo]]
) -> Dict[str, int]:
    """
    Link Live Photo pairs in the database using live_photo_pair_id.
    
    Both the image and video components get the same live_photo_pair_id UUID.
    
    Args:
        db_conn: Database connection
        pairs: List of (image_file, video_file) tuples
        
    Returns:
        Dictionary with statistics (pairs_linked, files_updated)
    """
    logger.info(f"Linking Live Photo pairs: {{'count': {len(pairs)}}}")
    
    files_updated = 0
    
    for image_file, video_file in pairs:
        # Generate a unique pair ID
        pair_id = str(uuid.uuid4())
        
        # Update both files with the pair ID
        for file_info in [image_file, video_file]:
            if file_info.media_item_id:
                cursor = db_conn.execute(
                    """
                    UPDATE media_items
                    SET live_photo_pair_id = ?
                    WHERE media_item_id = ?
                    """,
                    (pair_id, file_info.media_item_id)
                )
                if cursor.rowcount > 0:
                    files_updated += 1
                cursor.close()
            else:
                # If media_item_id not provided, update by path
                cursor = db_conn.execute(
                    """
                    UPDATE media_items
                    SET live_photo_pair_id = ?
                    WHERE relative_path = ?
                    """,
                    (pair_id, file_info.relative_path)
                )
                if cursor.rowcount > 0:
                    files_updated += 1
                cursor.close()
        
        logger.debug(f"Linked Live Photo pair: {{'pair_id': {pair_id!r}}}")
    
    db_conn.commit()
    
    stats = {
        'pairs_linked': len(pairs),
        'files_updated': files_updated,
    }
    
    logger.info(f"Live Photo linking completed: {stats}")
    
    return stats


def detect_and_link_live_photos(db_path: str, scan_run_id: str) -> Dict[str, int]:
    """
    Detect and link Live Photos for a scan run.
    
    This is a convenience function that:
    1. Queries all media items from the scan run
    2. Detects Live Photo pairs
    3. Links them in the database
    
    Args:
        db_path: Path to database (string or Path)
        scan_run_id: Scan run ID to process
        
    Returns:
        Dictionary with statistics
    """
    from pathlib import Path
    from ..database import DatabaseConnection
    
    logger.info(f"Processing Live Photos for scan_run {scan_run_id}")
    
    db_conn = DatabaseConnection(Path(db_path))
    conn = db_conn.connect()
    
    try:
        # Get all media items from this scan run
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
        
        # Detect pairs
        pairs = detect_live_photo_pairs(files)
        
        # Link pairs
        if pairs:
            stats = link_live_photo_pairs(conn, pairs)
        else:
            logger.info("No Live Photo pairs detected")
            stats = {'pairs_linked': 0, 'files_updated': 0}
        
        conn.commit()
        return stats
        
    finally:
        conn.close()
