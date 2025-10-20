"""File discovery module for media scanner.

Walks directory tree to identify media files and their JSON sidecars.
"""

import logging
import time
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
        logger.error(f"Target media path does not exist: {target_media_path}")
        return
    
    if not target_media_path.is_dir():
        logger.error(f"Target media path is not a directory: {target_media_path}")
        return
    
    logger.info(f"Starting file discovery from: {target_media_path}")
    
    # Detect Google Takeout structure (same logic as album_discovery)
    # scan_root is where albums actually live (excludes Takeout/Google Photos prefix)
    google_photos_path = target_media_path / "Takeout" / "Google Photos"
    if google_photos_path.exists() and google_photos_path.is_dir():
        logger.debug(f"Using scan root: {google_photos_path}")
        scan_root = google_photos_path
    else:
        logger.debug(f"Using scan root: {target_media_path}")
        scan_root = target_media_path
    
    # Build a map of JSON sidecars for efficient lookup
    # Key: media file path (e.g., parent/IMG_1234.jpg)
    # Value: Path to JSON sidecar file
    json_sidecars: dict[Path, Path] = {}
    
    # First pass: collect all JSON sidecars
    # CRITICAL: Scan from scan_root, not target_media_path
    for json_path in scan_root.rglob("*.json"):
        if not should_scan_file(json_path):
            continue
        
        # Check if this is a sidecar (not album metadata.json)
        if json_path.name == "metadata.json":
            continue  # Skip album metadata files
        
        # Google Takeout sidecar patterns (Windows MAX_PATH truncation):
        # Full: IMG_1234.jpg.supplemental-metadata.json (27 chars)
        # Truncated variants due to Windows 260-char path limit:
        #   - .supplemental-metadat.json (25 chars)
        #   - .supplemental-metada.json (24 chars)
        #   - .supplemental-metad.json (22 chars)
        #   - .supplemental-meta.json (21 chars)
        #   - .supplemental-met.json (20 chars)
        #   - .supplemental-me.json (18 chars)
        #   - .supplemental-m.json (17 chars)
        #   - .supplemental-.json (16 chars)
        #   - .supplementa.json (15 chars)
        #   - .supplemen.json (15 chars)
        #   - .suppleme.json (14 chars)
        #   - .supplem.json (13 chars)
        #   - .supple.json (12 chars)
        #   - .suppl.json (11 chars)
        #   - .supp.json (10 chars)
        #   - .sup.json (9 chars)
        #   - .su.json (8 chars)
        #   - .s.json (7 chars)
        #   - .json (5 chars) - alternative pattern for very long filenames
        
        parent_dir = json_path.parent
        filename = json_path.name
        
        # Try to extract media filename from sidecar filename
        media_filename = None
        
        # Pattern matching optimization: Use filename length to predict truncation level
        # This reduces checks from ~16 to 1-3 in most cases
        filename_len = len(filename)
        
        # Pattern 1: Full .supplemental-metadata.json or .supplemental-* variants (MOST COMMON)
        # Length-based heuristic: if filename is long enough, try full pattern first
        if filename_len > 30 and '.supplemental-metadata' in filename:
            # Full pattern: photo.jpg.supplemental-metadata.json (27 chars + base)
            media_filename = filename.split('.supplemental-metadata')[0]
        elif filename_len > 28 and '.supplemental-metadat' in filename:
            # Truncated: .supplemental-metadat.json (25 chars)
            media_filename = filename.split('.supplemental-metadat')[0]
        elif filename_len > 25 and '.supplemental-metad' in filename:
            # Truncated: .supplemental-metad.json (22 chars)
            media_filename = filename.split('.supplemental-metad')[0]
        elif filename_len > 24 and '.supplemental-meta' in filename:
            # Truncated: .supplemental-meta.json (21 chars)
            media_filename = filename.split('.supplemental-meta')[0]
        elif filename_len > 21 and '.supplemental-me' in filename:
            # Truncated: .supplemental-me.json (18 chars)
            media_filename = filename.split('.supplemental-me')[0]
        elif '.supplemental-' in filename:
            # Any other .supplemental-* variant (catch remaining truncations)
            media_filename = filename.split('.supplemental-')[0]
        
        # Pattern 2: .supplemen* variants (less common, more heavily truncated)
        elif filename_len > 18 and '.supplemen' in filename:
            # Truncated: .supplemen.json (15 chars)
            media_filename = filename.split('.supplemen')[0]
        elif filename_len > 17 and '.suppleme' in filename:
            # Truncated: .suppleme.json (14 chars)
            media_filename = filename.split('.suppleme')[0]
        elif filename_len > 16 and '.supplem' in filename:
            # Truncated: .supplem.json (13 chars)
            media_filename = filename.split('.supplem')[0]
        elif filename_len > 15 and '.supple' in filename:
            # Truncated: .supple.json (12 chars)
            media_filename = filename.split('.supple')[0]
        elif filename_len > 14 and '.suppl' in filename:
            # Truncated: .suppl.json (11 chars)
            media_filename = filename.split('.suppl')[0]
        elif filename_len > 13 and '.supp' in filename:
            # Truncated: .supp.json (10 chars)
            media_filename = filename.split('.supp')[0]
        
        # Pattern 3: Very heavily truncated (rare)
        elif filename_len > 12 and '.sup.' in filename and filename.endswith('.json'):
            # Truncated: .sup.json (9 chars) - need .json check to avoid false positives
            media_filename = filename.split('.sup.')[0]
        elif filename_len > 11 and '.su.' in filename and filename.endswith('.json'):
            # Truncated: .su.json (8 chars)
            media_filename = filename.split('.su.')[0]
        elif filename_len > 10 and '.s.' in filename and filename.endswith('.json'):
            # Truncated: .s.json (7 chars)
            media_filename = filename.split('.s.')[0]
        
        # Pattern 4: Alternative .json pattern (for very long filenames, rare)
        elif filename.endswith('.json'):
            # Alternative pattern: photo.json (without .supplemental prefix)
            # Used when media filename is extremely long
            media_filename = filename[:-5]
        
        if media_filename:
            key = parent_dir / media_filename
            json_sidecars[key] = json_path
    
    logger.info(f"Found {len(json_sidecars)} JSON sidecar files")
    
    # Second pass: discover all files and pair with sidecars
    logger.info("Discovering media files (this may take several minutes for large libraries)...")
    files_discovered = 0
    files_with_sidecars = 0
    progress_interval = 1000  # Log every 1000 files
    
    # Time-based progress logging
    discovery_start_time = time.time()
    last_progress_time = discovery_start_time
    time_progress_interval = 2.0  # Log every 2 seconds
    
    # CRITICAL: Scan from scan_root, not target_media_path
    for file_path in scan_root.rglob("*"):
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
        # CRITICAL: Use scan_root, not target_media_path, to exclude "Takeout/Google Photos" prefix
        # This makes paths portable (e.g., "Photos from 2023/IMG_1234.jpg" instead of "Takeout/Google Photos/Photos from 2023/IMG_1234.jpg")
        try:
            relative_path = file_path.relative_to(scan_root)
        except ValueError:
            logger.warning(f"File is not relative to scan root: {file_path}")
            continue
        
        # Get album folder path (relative to scan_root) for album_id lookup
        album_folder_path = file_path.parent.relative_to(scan_root)
        
        # Check for JSON sidecar
        # For edited files (e.g., IMG_1234-edited.jpg), look for original's sidecar
        # (e.g., IMG_1234.jpg.supplemental-metadata.json)
        # For tilde duplicates (e.g., IMG~2.jpg), try exact match first, then original
        sidecar_lookup_path = file_path
        
        if '-edited' in file_path.stem:
            # Strip -edited suffix to find original's sidecar
            original_stem = file_path.stem.rsplit('-edited', 1)[0]
            sidecar_lookup_path = file_path.parent / f"{original_stem}{file_path.suffix}"
        
        json_sidecar_path = json_sidecars.get(sidecar_lookup_path)
        
        # If not found and filename has tilde suffix (e.g., IMG~2.jpg), try original
        if not json_sidecar_path and '~' in file_path.stem:
            # Strip ~N suffix to find original's sidecar
            original_stem = file_path.stem.split('~')[0]
            original_lookup_path = file_path.parent / f"{original_stem}{file_path.suffix}"
            json_sidecar_path = json_sidecars.get(original_lookup_path)
        
        # If still not found, try prefix matching for alternative .json pattern
        # This handles cases where the sidecar filename itself is truncated
        # Example: photo_very_long_name.jpg → photo_very_long.json (truncated)
        if not json_sidecar_path:
            # Look for any .json file in same directory that is a prefix of the media filename
            media_stem = file_path.stem
            media_stem_len = len(media_stem)
            
            for candidate_path, candidate_sidecar in json_sidecars.items():
                # Check if in same directory
                if candidate_path.parent != file_path.parent:
                    continue
                # Check if sidecar is .json (not .supplemental-*.json)
                if not candidate_sidecar.name.endswith('.json'):
                    continue
                if '.supplemental' in candidate_sidecar.name:
                    continue
                
                # Length-based optimization: skip if lengths don't make sense
                candidate_stem = candidate_sidecar.stem  # Remove .json
                candidate_len = len(candidate_stem)
                
                # Skip if candidate is longer than media (can't be truncated version)
                if candidate_len >= media_stem_len:
                    continue
                # Skip if candidate is too short (likely different file)
                # Allow up to 50 characters of truncation
                if candidate_len < media_stem_len - 50:
                    continue
                # Require minimum length to avoid false positives
                if candidate_len < 10:
                    continue
                
                # Check if sidecar stem is a prefix of media stem
                # OR if media stem is a prefix of sidecar stem (both truncated from same base)
                if media_stem.startswith(candidate_stem):
                    json_sidecar_path = candidate_sidecar
                    break
                # Also check reverse: media might be truncated shorter than sidecar
                # Example: Screenshot_...aa.json vs Screenshot_...aaf.jpg
                if candidate_stem.startswith(media_stem):
                    json_sidecar_path = candidate_sidecar
                    break
        
        if json_sidecar_path:
            files_with_sidecars += 1
        
        files_discovered += 1
        
        # Progress logging (both count-based and time-based)
        current_time = time.time()
        if files_discovered % progress_interval == 0 or (current_time - last_progress_time) >= time_progress_interval:
            elapsed = current_time - discovery_start_time
            rate = files_discovered / elapsed if elapsed > 0 else 0
            logger.info(
                f"Discovery progress: {files_discovered} files found, {files_with_sidecars} with sidecars "
                f"({elapsed:.1f}s elapsed, {rate:.0f} files/sec)"
            )
            last_progress_time = current_time
        
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
        total_discovery_time = time.time() - discovery_start_time
        logger.info(
            f"File discovery complete: {files_discovered} files discovered, "
            f"{files_with_sidecars} with JSON sidecars (took {total_discovery_time:.1f}s)"
        )
