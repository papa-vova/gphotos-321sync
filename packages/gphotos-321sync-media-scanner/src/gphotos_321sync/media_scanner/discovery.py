"""File discovery for Google Takeout exports.

Discovers all media files and pairs them with JSON sidecars.
Handles Google Takeout directory structure and various edge cases.
"""

import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, List

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


@dataclass
class DiscoveryResult:
    """Result of file discovery operation.
    
    Attributes:
        files: List of discovered media files
        json_sidecar_count: Number of unique JSON sidecar files found
        paired_sidecars: Set of sidecar paths that were successfully paired
        all_sidecars: Set of all discovered sidecar paths (for orphan detection)
    """
    files: List[FileInfo]
    json_sidecar_count: int
    paired_sidecars: set[Path]
    all_sidecars: set[Path]


def discover_files_with_stats(target_media_path: Path) -> DiscoveryResult:
    """Discover all media files and return statistics.
    
    This is a wrapper around discover_files() that collects all results
    and returns both the files and the count of unique JSON sidecars.
    
    Args:
        target_media_path: Target media directory to scan (ABSOLUTE path)
        
    Returns:
        DiscoveryResult with files list, sidecar counts, and tracking sets
    """
    files = list(discover_files(target_media_path))
    
    # Track unique JSON sidecars (paired with media files)
    paired_sidecars = set()
    for file_info in files:
        if file_info.json_sidecar_path:
            paired_sidecars.add(file_info.json_sidecar_path)
    
    # Discover ALL JSON sidecars (including orphaned ones)
    # This requires scanning the directory again, but only for JSON files
    all_sidecars = set()
    google_photos_path = target_media_path / "Takeout" / "Google Photos"
    scan_root = google_photos_path if google_photos_path.exists() else target_media_path
    
    for json_path in scan_root.rglob("*.json"):
        if json_path.name != "metadata.json":  # Skip album metadata
            all_sidecars.add(json_path)
    
    return DiscoveryResult(
        files=files,
        json_sidecar_count=len(paired_sidecars),
        paired_sidecars=paired_sidecars,
        all_sidecars=all_sidecars
    )


def _collect_media_files(scan_root: Path) -> tuple[list[Path], list[Path], dict[Path, set[str]]]:
    """Collect all media and JSON files in the directory tree.
    
    Args:
        scan_root: Root directory to scan
        
    Returns:
        Tuple of (media_files, json_files, all_files_dict)
    """
    all_files: dict[Path, set[str]] = {}  # Key: parent_dir, Value: set of filenames in that dir
    json_files: list[Path] = []  # All JSON sidecar files
    media_files: list[Path] = []  # All potential media files
    
    logger.info("Collecting all files...")
    for file_path in scan_root.rglob("*"):
        if file_path.is_dir():
            continue
        if not should_scan_file(file_path):
            continue
        
        parent_dir = file_path.parent
        if parent_dir not in all_files:
            all_files[parent_dir] = set()
        all_files[parent_dir].add(file_path.name)
        
        if file_path.suffix.lower() == ".json":
            if file_path.name != "metadata.json":  # Skip album metadata
                json_files.append(file_path)
        else:
            media_files.append(file_path)
    
    logger.info(f"Files collected: {{'media': {len(media_files)}, 'json_sidecars': {len(json_files)}}}")
    return media_files, json_files, all_files


def _create_file_info(
    file_path: Path, 
    scan_root: Path, 
    json_sidecars: dict[Path, Path]
) -> FileInfo:
    """Create FileInfo object for a media file.
    
    Args:
        file_path: Path to the media file
        scan_root: Root directory for relative path calculation
        json_sidecars: Dictionary mapping media files to their JSON sidecars
        
    Returns:
        FileInfo object for the media file
    """
    # Calculate relative path from scan_root
    relative_path = file_path.relative_to(scan_root)
    
    # Calculate album folder path (parent of the file)
    album_folder_path = relative_path.parent
    
    # Get file size
    file_size = file_path.stat().st_size
    
    # Find JSON sidecar
    json_sidecar_path = json_sidecars.get(file_path)
    
    return FileInfo(
        file_path=file_path,
        relative_path=relative_path,
        album_folder_path=album_folder_path,
        json_sidecar_path=json_sidecar_path,
        file_size=file_size
    )


def _match_sidecar_patterns(
    json_files: list[Path], 
    media_files: list[Path], 
    all_files: dict[Path, set[str]]
) -> dict[Path, Path]:
    """Match JSON sidecars to media files using various patterns.
    
    Args:
        json_files: List of JSON sidecar files
        media_files: List of media files
        all_files: Dictionary of files by directory
        
    Returns:
        Dictionary mapping media files to their JSON sidecars
    """
    json_sidecars: dict[Path, Path] = {}
    
    # Track matching statistics
    happy_path_matches = 0
    heuristic_matches = 0
    unmatched_sidecars = []
    
    for json_path in json_files:
        # Extract base filename without .json extension
        json_stem = json_path.stem
        
        # Try to find matching media file
        media_file_found = False
        
        # Strategy 1: Direct filename match (happy path)
        # Look for media file with same name as JSON sidecar
        parent_dir = json_path.parent
        if parent_dir in all_files:
            for filename in all_files[parent_dir]:
                if filename == json_stem:
                    # Found exact match
                    media_file_path = parent_dir / filename
                    if media_file_path in media_files:
                        json_sidecars[media_file_path] = json_path
                        happy_path_matches += 1
                        media_file_found = True
                        break
        
        if media_file_found:
            continue
            
        # Strategy 2: Handle Google Takeout sidecar patterns
        # Look for media files that match the JSON sidecar pattern
        for media_path in media_files:
            if media_path.parent != json_path.parent:
                continue
                
            media_stem = media_path.stem
            
            # Check if JSON sidecar matches media file
            if json_stem == media_stem:
                json_sidecars[media_path] = json_path
                happy_path_matches += 1
                media_file_found = True
                break
        
        if not media_file_found:
            unmatched_sidecars.append(json_path)
    
    logger.info(f"Sidecar matching complete: {{'happy_path': {happy_path_matches}, 'heuristic': {heuristic_matches}, 'unmatched': {len(unmatched_sidecars)}}}")
    
    return json_sidecars


def discover_files(
    target_media_path: Path
) -> Iterator[FileInfo]:
    """Discover all media files in the directory tree.
    
    Automatically detects Google Takeout structure and makes paths relative to album root.
    
    Args:
        target_media_path: Target media directory to scan (ABSOLUTE path)
        
    Yields:
        FileInfo objects for each discovered media file
        
    Note:
        - Filters out system/hidden/temp files via should_scan_file()
        - Does NOT filter by extension (MIME detection determines media type)
        - Pairs media files with .json sidecars when found
        - JSON sidecars are identified by naming pattern: <filename>.json
        - relative_path and album_folder_path are relative to scan_root (excludes Takeout/Google Photos)
    """
    if not target_media_path.exists():
        logger.error(f"Target media path does not exist: {{'path': {str(target_media_path)!r}}}")
        return
    
    if not target_media_path.is_dir():
        logger.error(f"Target media path is not a directory: {{'path': {str(target_media_path)!r}}}")
        return
    
    logger.info(f"Starting file discovery: {{'path': {str(target_media_path)!r}}}")
    
    # Detect Google Takeout structure (same logic as album_discovery)
    # scan_root is where albums actually live (excludes Takeout/Google Photos prefix)
    google_photos_path = target_media_path / "Takeout" / "Google Photos"
    if google_photos_path.exists() and google_photos_path.is_dir():
        logger.debug(f"Using scan root: {{'path': {str(google_photos_path)!r}}}")
        scan_root = google_photos_path
    else:
        logger.debug(f"Using scan root: {{'path': {str(target_media_path)!r}}}")
        scan_root = target_media_path
    
    # Collect all files in the directory tree
    media_files, json_files, all_files = _collect_media_files(scan_root)
    
    # Match JSON sidecars to media files
    json_sidecars = _match_sidecar_patterns(json_files, media_files, all_files)
    
    # Process each media file and yield FileInfo objects
    files_discovered = 0
    files_with_sidecars = 0
    discovery_start_time = time.time()
    last_progress_time = discovery_start_time
    progress_interval = 1000  # Log progress every 1000 files
    time_progress_interval = 30.0  # Log progress every 30 seconds
    
    for file_path in media_files:
        # Create FileInfo object for this media file
        file_info = _create_file_info(file_path, scan_root, json_sidecars)
        
        if file_info.json_sidecar_path:
            files_with_sidecars += 1
        
        files_discovered += 1
        
        # Progress logging (both count-based and time-based)
        current_time = time.time()
        if files_discovered % progress_interval == 0 or (current_time - last_progress_time) >= time_progress_interval:
            elapsed = current_time - discovery_start_time
            rate = files_discovered / elapsed if elapsed > 0 else 0
            logger.info(
                f"Discovery progress: {{'files_found': {files_discovered}, 'with_sidecars': {files_with_sidecars}, 'elapsed_seconds': {elapsed:.1f}, 'files_per_sec': {rate:.0f}}}"
            )
            last_progress_time = current_time
        
        yield file_info
    
    if files_discovered == 0:
        logger.warning(f"No media files discovered: {{'path': {str(target_media_path)!r}}}")
    else:
        total_discovery_time = time.time() - discovery_start_time
        logger.info(
            f"File discovery complete: {{'files_discovered': {files_discovered}, 'with_sidecars': {files_with_sidecars}, 'duration_seconds': {total_discovery_time:.1f}}}"
        )
