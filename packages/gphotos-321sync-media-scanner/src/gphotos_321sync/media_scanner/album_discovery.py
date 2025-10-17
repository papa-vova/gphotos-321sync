"""Album discovery and processing module.

Discovers albums from folder structure and metadata.json files.
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional
from datetime import datetime

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
                    metadata['creation_timestamp'] = datetime.fromtimestamp(int(timestamp_str))
            except (ValueError, KeyError, TypeError) as e:
                logger.warning(f"Failed to parse creation timestamp in {metadata_path}: {e}")
        
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
        if 1900 <= year <= 2100:
            return year
    return None


def discover_albums(target_media_path: Path, album_dal: AlbumDAL, scan_run_id: str) -> Iterator[AlbumInfo]:
    """Discover and process albums from directory structure.
    
    Walks the directory tree to find:
    1. User albums: Folders with metadata.json
    2. Year-based albums: Folders named "Photos from YYYY"
    
    For each album:
    - Generates UUID5 album_id from folder path
    - Parses metadata.json if present (handles errors gracefully)
    - Inserts/updates album in database
    - Yields AlbumInfo for tracking
    
    Args:
        target_media_path: Target media directory to scan
        album_dal: Album data access layer for database operations
        scan_run_id: Current scan run ID
        
    Yields:
        AlbumInfo objects for each discovered album
        
    Note:
        - Every folder is treated as an album (album_id always generated)
        - Metadata parsing errors are logged and recorded in processing_errors
        - Albums are inserted into database immediately (needed before file processing)
    """
    if not target_media_path.exists():
        logger.error(f"Target media path does not exist: {target_media_path}")
        return
    
    if not target_media_path.is_dir():
        logger.error(f"Target media path is not a directory: {target_media_path}")
        return
    
    logger.info(f"Starting album discovery from: {target_media_path}")
    
    albums_discovered = 0
    user_albums = 0
    year_albums = 0
    errors = 0
    
    # Walk directory tree to find all folders
    for folder_path in target_media_path.rglob("*"):
        if not folder_path.is_dir():
            continue
        
        # Calculate relative path for album_id generation
        try:
            album_folder_path = folder_path.relative_to(target_media_path)
        except ValueError:
            logger.warning(f"Folder is not relative to target media path: {folder_path}")
            continue
        
        # Generate deterministic album_id from folder path
        album_id = album_dal.generate_album_id(str(album_folder_path))
        
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
                logger.error(f"Failed to parse album metadata {metadata_path}: {e}")
                status = 'error'
                errors += 1
                # Continue with default values
        
        # Check if this is a year-based album
        year = extract_year_from_folder(folder_path.name)
        if year is not None and not is_user_album:
            title = f"Photos from {year}"
            year_albums += 1
        
        # Insert/update album in database
        album_data = {
            'album_id': album_id,
            'album_folder_path': str(album_folder_path),
            'title': title,
            'description': description,
            'creation_timestamp': creation_timestamp,
            'access_level': access_level,
            'status': status,
            'scan_run_id': scan_run_id,
        }
        
        # Check if album already exists
        existing = album_dal.get_album_by_path(str(album_folder_path))
        if existing:
            # Update existing album
            album_dal.update_album(
                album_id=album_id,
                title=title,
                description=description,
                creation_timestamp=creation_timestamp,
                access_level=access_level,
                status=status,
                scan_run_id=scan_run_id,
                last_seen_timestamp=datetime.now()
            )
        else:
            # Insert new album
            album_dal.insert_album(album_data)
        
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
    
    logger.info(
        f"Album discovery complete: {albums_discovered} albums discovered "
        f"({user_albums} user albums, {year_albums} year-based albums, {errors} errors)"
    )
