"""Album discovery and processing module.

Discovers albums from folder structure and metadata.json files.
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional
from datetime import datetime, timezone

from gphotos_321sync.common import normalize_path
from .dal.albums import AlbumDAL
from .errors import ParseError

logger = logging.getLogger(__name__)


@dataclass
class AlbumInfo:
    """Information about a discovered album.
    
    Attributes:
        album_id: UUID5 generated from folder path
        album_folder_path: Path relative to scan root
        title: Album title
        description: Album description (optional)
        creation_timestamp: When album was created (optional)
        access_level: Access level from metadata (optional)
        is_user_album: True if has metadata.json, False for year-based
        metadata_path: Path to metadata.json if exists
    """
    album_id: str
    album_folder_path: Path
    title: str
    description: Optional[str] = None
    creation_timestamp: Optional[datetime] = None
    access_level: Optional[str] = None
    is_user_album: bool = False
    metadata_path: Optional[Path] = None


def parse_album_metadata(metadata_path: Path) -> dict:
    """Parse album metadata.json file.
    
    Args:
        metadata_path: Path to metadata.json file
        
    Returns:
        Dictionary with album metadata
        
    Raises:
        ParseError: If JSON is invalid or missing required fields
    """
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract fields (all optional in Google Takeout)
        metadata = {
            'title': data.get('title'),
            'description': data.get('description'),
            'access_level': data.get('access'),
        }
        
        # Parse creation timestamp if present
        if 'date' in data:
            try:
                # Google Takeout format: {"timestamp": "1234567890"}
                timestamp_data = data['date']
                if isinstance(timestamp_data, dict) and 'timestamp' in timestamp_data:
                    timestamp_str = timestamp_data['timestamp']
                    metadata['creation_timestamp'] = datetime.fromtimestamp(int(timestamp_str), tz=timezone.utc)
            except (ValueError, KeyError, TypeError) as e:
                logger.warning(f"Failed to parse creation timestamp: {{'path': {str(metadata_path)!r}, 'error': {str(e)!r}}}")
        
        return metadata
        
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON in {metadata_path}: {e}")
    except OSError as e:
        raise ParseError(f"Failed to read {metadata_path}: {e}")


def extract_year_from_folder(folder_name: str) -> Optional[int]:
    """Extract year from folder name like 'Photos from 2023'.
    
    Args:
        folder_name: Folder name to parse
        
    Returns:
        Year as integer, or None if not a year-based folder
    """
    # Match patterns like "Photos from 2023", "Photos from YYYY"
    match = re.match(r'Photos from (\d{4})', folder_name, re.IGNORECASE)
    if match:
        year = int(match.group(1))
        # Sanity check: reasonable year range
        if 1900 <= year <= 2200:
            return year
    return None


def discover_albums(target_media_path: Path, album_dal: AlbumDAL, scan_run_id: str) -> Iterator[AlbumInfo]:
    """Discover and process albums from directory structure.
    
    IMPORTANT: Google Takeout Structure Detection
    - Automatically detects "Takeout/Google Photos" subfolder
    - If found, ONLY scans albums from within "Takeout/Google Photos/"
    - Otherwise, scans albums from target_media_path directly
    
    Album Discovery:
    1. User albums: Folders with metadata.json
    2. Year-based albums: Folders named "Photos from YYYY"
    
    Album ID Generation (Deterministic UUID5):
    - Uses ONLY the album folder name (e.g., "Photos from 2023")
    - Excludes target_media_path prefix
    - Excludes "Takeout/Google Photos" prefix if present
    - This ensures consistent IDs regardless of where Takeout is extracted
    
    For each album:
    - Generates UUID5 album_id from album name only
    - Parses metadata.json if present (handles errors gracefully)
    - Inserts/updates album in database
    - Yields AlbumInfo for tracking
    
    Args:
        target_media_path: Root scan directory (e.g., C:\\takeout_tests)
        album_dal: Album data access layer for database operations
        scan_run_id: Current scan run ID
        
    Yields:
        AlbumInfo objects for each discovered album
        
    Note:
        - Google Photos doesn't support nested albums (only one level)
        - Every folder is treated as an album (album_id always generated)
        - Metadata parsing errors are logged and recorded in processing_errors
        - Albums are inserted into database immediately (needed before file processing)
    """
    if not target_media_path.exists():
        raise FileNotFoundError(
            f"Target media path does not exist: {target_media_path}\n"
            f"Please verify the path and try again."
        )
    
    if not target_media_path.is_dir():
        raise NotADirectoryError(
            f"Target media path is not a directory: {target_media_path}\n"
            f"Please provide a valid directory path."
        )
    
    logger.debug(f"Starting album discovery: {{'path': {str(target_media_path)!r}, 'type': {type(target_media_path).__name__!r}}}")
    
    # Detect Google Takeout structure: Takeout/Google Photos/
    # This is CRITICAL - Google Takeout places all albums in this subfolder
    # scan_root is where albums actually live (excludes Takeout/Google Photos prefix)
    google_photos_path = target_media_path / "Takeout" / "Google Photos"
    if google_photos_path.exists() and google_photos_path.is_dir():
        logger.info("✓ Detected Google Takeout structure")
        logger.info(f"  Scanning albums from: {google_photos_path}")
        scan_root = google_photos_path
    else:
        logger.info("Using flat structure (no Takeout/Google Photos found)")
        logger.info(f"  Scanning albums from: {target_media_path}")
        scan_root = target_media_path
    
    albums_discovered = 0
    user_albums = 0
    year_albums = 0
    errors = 0
    
    # Walk directory to find album folders (Google Photos doesn't support nested albums)
    logger.debug(f"Scanning for albums: {{'path': {str(scan_root)!r}}}")
    folder_list = list(scan_root.iterdir())
    logger.debug(f"Found items in scan directory: {{'count': {len(folder_list)}}}")
    for folder_path in folder_list:
        if not folder_path.is_dir():
            continue
        
        # Calculate relative path for database storage
        # CRITICAL: Use scan_root, not target_media_path, to exclude "Takeout/Google Photos" prefix
        # This makes paths portable (e.g., "Photos from 2023" instead of "Takeout/Google Photos/Photos from 2023")
        try:
            album_folder_path = folder_path.relative_to(scan_root)
        except ValueError:
            logger.warning(f"Folder not relative to scan root: {{'path': {str(folder_path)!r}}}")
            continue
        
        # Generate deterministic album_id from ALBUM NAME ONLY
        # Exclude target_media_path and "Takeout/Google Photos" prefix
        # This ensures consistent IDs regardless of extraction location
        album_name = folder_path.name  # Just the folder name (e.g., "Photos from 2023")
        album_id = album_dal.generate_album_id(album_name)
        
        # Check for metadata.json (user album)
        metadata_path = folder_path / "metadata.json"
        is_user_album = metadata_path.exists()
        
        # Initialize album info
        title = folder_path.name  # Default to folder name
        description = None
        creation_timestamp = None
        access_level = None
        status = 'present'
        
        # Parse metadata.json if present
        if is_user_album:
            try:
                metadata = parse_album_metadata(metadata_path)
                title = metadata.get('title') or title
                description = metadata.get('description')
                creation_timestamp = metadata.get('creation_timestamp')
                access_level = metadata.get('access_level')
                user_albums += 1
                
            except ParseError as e:
                logger.warning(f"Failed to parse album metadata: {{'path': {str(metadata_path)!r}, 'error': {str(e)!r}}}")
                status = 'error'
                errors += 1
                # Continue with default values
        
        # Check if this is a year-based album
        year = extract_year_from_folder(folder_path.name)
        if year is not None and not is_user_album:
            title = f"Photos from {year}"
            year_albums += 1
        
        # Normalize album folder path for database storage (forward slashes, NFC)
        normalized_album_path = normalize_path(str(album_folder_path))
        
        # Upsert album in database (insert if new, update if exists)
        # The DAL handles the existence check and appropriate logging
        album_data = {
            'album_id': album_id,
            'album_folder_path': normalized_album_path,
            'title': title,
            'description': description,
            'creation_timestamp': creation_timestamp,
            'access_level': access_level,
            'status': status,
            'scan_run_id': scan_run_id,
        }
        album_dal.upsert_album(album_data)
        
        albums_discovered += 1
        
        # Yield album info
        yield AlbumInfo(
            album_id=album_id,
            album_folder_path=album_folder_path,
            title=title,
            description=description,
            creation_timestamp=creation_timestamp,
            access_level=access_level,
            is_user_album=is_user_album,
            metadata_path=metadata_path if is_user_album else None
        )
    
    if albums_discovered == 0:
        raise RuntimeError(
            f"No albums discovered in: {target_media_path}\n"
            f"The directory exists but contains no subdirectories.\n"
            f"Please add albums (folders) to the target media path before running the scan."
        )
    
    logger.info(
        f"Album discovery complete: {{'total': {albums_discovered}, 'user_albums': {user_albums}, 'year_albums': {year_albums}, 'errors': {errors}}}"
    )
