"""File discovery module for media scanner.

Walks directory tree to identify media files and their JSON sidecars.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from .path_utils import should_scan_file

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """Information about a discovered media file.
    
    Attributes:
        file_path: Absolute path to the media file
        relative_path: Path relative to scan root
        album_folder_path: Album folder path (relative to scan root)
        json_sidecar_path: Path to JSON sidecar if exists
        file_size: Size of the file in bytes
    """
    file_path: Path
    relative_path: Path
    album_folder_path: Path
    json_sidecar_path: Optional[Path]
    file_size: int


def discover_files(target_media_path: Path) -> Iterator[FileInfo]:
    """Discover all media files in the directory tree.
    
    Walks the directory tree starting from target_media_path, identifies media files
    and their JSON sidecars, and yields FileInfo objects for each media file.
    
    Args:
        target_media_path: Target media directory to scan
        
    Yields:
        FileInfo objects for each discovered media file
        
    Note:
        - Filters out system/hidden/temp files via should_scan_file()
        - Does NOT filter by extension (MIME detection determines media type)
        - Pairs media files with .json sidecars when found
        - JSON sidecars are identified by naming pattern: <filename>.json
    """
    if not target_media_path.exists():
        logger.error(f"Target media path does not exist: {target_media_path}")
        return
    
    if not target_media_path.is_dir():
        logger.error(f"Target media path is not a directory: {target_media_path}")
        return
    
    logger.info(f"Starting file discovery from: {target_media_path}")
    
    # Build a map of JSON sidecars for efficient lookup
    # Key: media file path (e.g., parent/IMG_1234.jpg)
    # Value: Path to JSON sidecar file
    json_sidecars: dict[Path, Path] = {}
    
    # First pass: collect all JSON sidecars
    for json_path in target_media_path.rglob("*.json"):
        if not should_scan_file(json_path):
            continue
        
        # Check if this is a sidecar (not album metadata.json)
        if json_path.name == "metadata.json":
            continue  # Skip album metadata files
        
        # Google Takeout sidecar patterns:
        # 1. IMG_1234.jpg.supplemental-metadata.json (standard)
        # 2. IMG_1234.jpg.supplemental-me.json (truncated)
        # 3. IMG_1234.jpg.supplemental-metadat.json (truncated)
        # 4. IMG_1234.jpg.supplemental-metad.json (truncated)
        # 5. IMG_1234.jpg.json (legacy)
        
        parent_dir = json_path.parent
        filename = json_path.name
        
        # Try to extract media filename from sidecar filename
        media_filename = None
        
        # Pattern 1-4: .supplemental-*.json variants
        if '.supplemental-' in filename:
            # Split on .supplemental- and take everything before it
            media_filename = filename.split('.supplemental-')[0]
        # Pattern 5: .json (legacy)
        elif filename.endswith('.json'):
            # Remove .json extension
            media_filename = filename[:-5]
        
        if media_filename:
            key = parent_dir / media_filename
            json_sidecars[key] = json_path
    
    logger.info(f"Found {len(json_sidecars)} JSON sidecar files")
    
    # Second pass: discover all files and pair with sidecars
    files_discovered = 0
    files_with_sidecars = 0
    
    for file_path in target_media_path.rglob("*"):
        # Skip directories
        if file_path.is_dir():
            continue
        
        # Skip files that shouldn't be scanned
        if not should_scan_file(file_path):
            continue
        
        # Skip JSON files (they're sidecars, not media)
        if file_path.suffix.lower() == ".json":
            continue
        
        # Get file size
        try:
            file_size = file_path.stat().st_size
        except OSError as e:
            logger.warning(f"Failed to get file size for {file_path}: {e}")
            continue
        
        # Calculate relative path
        try:
            relative_path = file_path.relative_to(target_media_path)
        except ValueError:
            logger.warning(f"File is not relative to target media path: {file_path}")
            continue
        
        # Get album folder path (relative) for album_id
        album_folder_path = file_path.parent.relative_to(target_media_path)
        
        # Check for JSON sidecar
        # For edited files (e.g., IMG_1234-edited.jpg), look for original's sidecar
        # (e.g., IMG_1234.jpg.supplemental-metadata.json)
        sidecar_lookup_path = file_path
        if '-edited' in file_path.stem:
            # Strip -edited suffix to find original's sidecar
            original_stem = file_path.stem.rsplit('-edited', 1)[0]
            sidecar_lookup_path = file_path.parent / f"{original_stem}{file_path.suffix}"
        
        json_sidecar_path = json_sidecars.get(sidecar_lookup_path)
        if json_sidecar_path:
            files_with_sidecars += 1
        
        files_discovered += 1
        
        yield FileInfo(
            file_path=file_path,
            relative_path=relative_path,
            album_folder_path=album_folder_path,
            json_sidecar_path=json_sidecar_path,
            file_size=file_size
        )
    
    if files_discovered == 0:
        logger.warning(f"No media files discovered in: {target_media_path}")
    else:
        logger.info(
            f"File discovery complete: {files_discovered} files discovered, "
            f"{files_with_sidecars} with JSON sidecars"
        )
