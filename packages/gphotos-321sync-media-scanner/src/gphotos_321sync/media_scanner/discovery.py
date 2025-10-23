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
    
    # STEP 1: Collect ALL files in one pass (both media and JSON)
    # Build sets for efficient string-based lookup
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
    
    # STEP 2: Match JSON sidecars to media files using PURE string matching
    # Build a map of JSON sidecars for efficient lookup
    # Key: media file path (e.g., parent/IMG_1234.jpg)
    # Value: Path to JSON sidecar file
    json_sidecars: dict[Path, Path] = {}
    
    # Track matching statistics
    happy_path_matches = 0
    heuristic_matches = 0
    unmatched_sidecars = []
    
    for json_path in json_files:
        
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
        
        # Get available media filenames in this directory for string matching
        available_media_files = all_files.get(parent_dir, set())
        
        # Debug logging
        if not available_media_files:
            logger.debug(f"No media files found in directory: {{'dir': {str(parent_dir)!r}, 'sidecar': {json_path.name!r}}}")
        
        # Try to extract media filename from sidecar filename
        media_filename = None
        heuristic_code = None  # Track which heuristic was used
        
        # Extract duplicate numbered suffix (e.g., "(1)", "(2)") before .json if present
        # Pattern: filename.ext.supplemental-metadata(1).json
        # The media file will be: filename(1).ext
        # This handles duplicate files in Google Takeout exports
        duplicate_suffix = ""
        has_duplicate_suffix = False
        if filename.endswith('.json'):
            # Check for (N) pattern before .json
            duplicate_pattern = r'\((\d+)\)\.json$'
            match = re.search(duplicate_pattern, filename)
            if match:
                # Extract the (N) suffix and remove it for pattern matching
                duplicate_suffix = match.group(0)[:-5]  # Extract "(N)" without ".json"
                filename = filename[:match.start()] + '.json'
                has_duplicate_suffix = True
        
        # Pattern matching optimization: Use filename length to predict truncation level
        # This reduces checks from ~16 to 1-3 in most cases
        filename_len = len(filename)
        
        # HEURISTIC: Sidecars with duplicate suffix but no extension in base name
        # Pattern: [UNSET].supplemental-metadata(1).json -> [UNSET](1).jpg
        #          [Some Name].supplemental-metadata(2).json -> [Some Name](2).png
        # Google Photos creates these for files without proper metadata
        # MUST come BEFORE happy path because base name has no extension
        # Quick pre-check: skip if filename contains common media extension before .supplemental
        # This avoids computing base/base_ext for 99% of files
        if (has_duplicate_suffix and '.supplemental' in filename and 
            not any(f'.{ext}.supplemental' in filename for ext in 
                   ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'heic', 'tiff', 'tif',
                    'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv', '3gp', 'm4v'])):
            # Now extract base and verify no valid extension
            base = filename.split('.supplemental')[0]
            base_ext = base.split('.')[-1].lower() if '.' in base else ''
            valid_exts = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'heic', 'tiff', 'tif', 
                         'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv', '3gp', 'm4v'}
            
            # Double-check: only apply if base has NO valid extension
            if base_ext not in valid_exts:
                logger.debug(f"Applying no_extension heuristic: {{'base': {base!r}, 'duplicate_suffix': {duplicate_suffix!r}}}")
                # Base has no valid extension - try to find media file with duplicate suffix
                for ext in ['.jpg', '.jpeg', '.png', '.mp4', '.mov', '.heic', '.gif', '.webp']:
                    candidate_name = f"{base}{duplicate_suffix}{ext}"
                    logger.debug(f"Trying candidate: {candidate_name!r}, in set: {candidate_name in available_media_files}")
                    if candidate_name in available_media_files:
                        media_filename = candidate_name
                        heuristic_code = "no_extension_with_duplicate_suffix"
                        logger.debug(f"MATCHED: {candidate_name!r}")
                        # Clear duplicate_suffix since we already included it in media_filename
                        duplicate_suffix = ""
                        has_duplicate_suffix = False
                        break
                
                logger.debug(f"After no_extension heuristic: {{'media_filename': {media_filename!r}}}")
        
        # HAPPY PATH: Full .supplemental-metadata.json (standard Google Takeout pattern)
        if media_filename is None and filename_len > 30 and '.supplemental-metadata' in filename:
            # Full pattern: photo.jpg.supplemental-metadata.json (27 chars + base)
            media_filename = filename.split('.supplemental-metadata')[0]
            logger.debug(f"Happy path matched: {{'filename': {filename!r}, 'media_filename': {media_filename!r}, 'duplicate_suffix': {duplicate_suffix!r}}}")
            # No heuristic code - this is happy path
        # HEURISTIC: Truncated .supplemental-* patterns (Windows MAX_PATH truncation)
        elif media_filename is None and filename_len > 28 and '.supplemental-metadat' in filename:
            media_filename = filename.split('.supplemental-metadat')[0]
            heuristic_code = "truncated_supplemental_metadat"
        elif media_filename is None and filename_len > 25 and '.supplemental-metad' in filename:
            media_filename = filename.split('.supplemental-metad')[0]
            heuristic_code = "truncated_supplemental_metad"
        elif media_filename is None and filename_len > 24 and '.supplemental-meta' in filename:
            media_filename = filename.split('.supplemental-meta')[0]
            heuristic_code = "truncated_supplemental_meta"
        elif media_filename is None and filename_len > 21 and '.supplemental-me' in filename:
            media_filename = filename.split('.supplemental-me')[0]
            heuristic_code = "truncated_supplemental_me"
        elif media_filename is None and '.supplemental-' in filename:
            media_filename = filename.split('.supplemental-')[0]
            heuristic_code = "truncated_supplemental_other"
        
        # HEURISTIC: .supplemen* variants (heavily truncated)
        elif media_filename is None and filename_len > 18 and '.supplemen' in filename:
            media_filename = filename.split('.supplemen')[0]
            heuristic_code = "truncated_supplemen"
        elif media_filename is None and filename_len > 17 and '.suppleme' in filename:
            media_filename = filename.split('.suppleme')[0]
            heuristic_code = "truncated_suppleme"
        elif media_filename is None and filename_len > 16 and '.supplem' in filename:
            media_filename = filename.split('.supplem')[0]
            heuristic_code = "truncated_supplem"
        elif media_filename is None and filename_len > 15 and '.supple' in filename:
            media_filename = filename.split('.supple')[0]
            heuristic_code = "truncated_supple"
        elif media_filename is None and filename_len > 14 and '.suppl' in filename:
            media_filename = filename.split('.suppl')[0]
            heuristic_code = "truncated_suppl"
        elif media_filename is None and filename_len > 13 and '.supp' in filename:
            media_filename = filename.split('.supp')[0]
            heuristic_code = "truncated_supp"
        
        # HEURISTIC: Very heavily truncated (rare)
        elif media_filename is None and filename_len > 12 and '.sup.' in filename and filename.endswith('.json'):
            media_filename = filename.split('.sup.')[0]
            heuristic_code = "truncated_sup"
        elif media_filename is None and filename_len > 11 and '.su.' in filename and filename.endswith('.json'):
            media_filename = filename.split('.su.')[0]
            heuristic_code = "truncated_su"
        elif media_filename is None and filename_len > 10 and '.s.' in filename and filename.endswith('.json'):
            media_filename = filename.split('.s.')[0]
            heuristic_code = "truncated_s"
        
        # HEURISTIC: Duplicate sidecars without .supplemental-metadata
        # Pattern: "Screenshot_2022-04-21(1).json" -> "Screenshot_2022-04-21.jpg"
        # This handles duplicate JSON sidecars that don't have the supplemental-metadata pattern
        # MUST come before plain_json_extension fallback
        elif media_filename is None and has_duplicate_suffix and '.supplemental' not in filename:
            # Extract base name without (N).json
            base = json_path.stem.rsplit('(', 1)[0]  # Remove (N) suffix
            # Try common extensions
            for ext in ['.jpg', '.jpeg', '.png', '.mp4', '.mov', '.heic', '.gif', '.webp']:
                candidate_name = f"{base}{ext}"
                if candidate_name in available_media_files:
                    media_filename = candidate_name
                    heuristic_code = "duplicate_without_supplemental"
                    # Clear duplicate_suffix since it's already in the sidecar name, not media name
                    duplicate_suffix = ""
                    has_duplicate_suffix = False
                    break
        
        # HEURISTIC: Alternative .json pattern (for very long filenames, rare)
        # This is a fallback - should come AFTER all other specific patterns
        elif media_filename is None and filename.endswith('.json'):
            # Alternative pattern: photo.json (without .supplemental prefix)
            # Used when media filename is extremely long and gets truncated
            # Do PREFIX matching - find media file that starts with the sidecar base name
            base = filename[:-5]  # Remove .json
            # Find ALL media files that start with this base
            candidates = [f for f in available_media_files if f.startswith(base) and f != filename]
            # Only match if there's exactly ONE candidate (unambiguous)
            if len(candidates) == 1:
                media_filename = candidates[0]
                heuristic_code = "plain_json_extension"
            elif len(candidates) > 1:
                # Ambiguous - multiple files match this prefix
                logger.warning(
                    f"Ambiguous prefix match for sidecar: {{'filename': {json_path.name!r}, 'prefix': {base!r}, 'candidates': {candidates}}}"
                )
        
        if media_filename:
            # STEP 1: Add duplicate suffix FIRST (before extension guessing)
            # If there's a duplicate suffix (e.g., "(1)"), insert it before the extension
            # Example: image.png + (1) -> image(1).png
            if duplicate_suffix:
                logger.debug(f"Adding duplicate suffix: {{'media_filename': {media_filename!r}, 'duplicate_suffix': {duplicate_suffix!r}}}")
                
                # Check if media_filename has a valid extension
                # Can't use Path().suffix because "18.03.12 - 1" would return ".03"
                media_ext = media_filename.split('.')[-1].lower() if '.' in media_filename else ''
                valid_exts = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'heic', 'tiff', 'tif', 
                             'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv', '3gp', 'm4v'}
                
                if media_ext in valid_exts:
                    # Has valid extension - use Path to split properly
                    media_path = Path(media_filename)
                    stem = media_path.stem
                    suffix = media_path.suffix
                    media_filename = f"{stem}{duplicate_suffix}{suffix}"
                else:
                    # No valid extension - just append duplicate suffix at the end
                    media_filename = f"{media_filename}{duplicate_suffix}"
                
                logger.debug(f"After adding duplicate suffix: {{'media_filename': {media_filename!r}}}")
            
            # STEP 2: Extension guessing (AFTER duplicate suffix is added)
            # Pattern: "04.03.12 - 10(1)" -> "04.03.12 - 10(1).jpg"
            # This handles cases where the sidecar name doesn't include the media extension
            # ONLY apply if the media file doesn't exist as-is
            if media_filename not in available_media_files:
                # Check if media_filename has a valid media extension
                # Can't use Path().suffix because "04.03.12 - 10" would return ".10"
                media_ext = media_filename.split('.')[-1].lower() if '.' in media_filename else ''
                valid_exts = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'heic', 'tiff', 'tif', 
                             'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv', '3gp', 'm4v'}
                
                if media_ext not in valid_exts:
                    # Media filename has no valid extension - try to guess it
                    base = media_filename
                    # Try common extensions
                    for ext in ['.jpg', '.jpeg', '.png', '.mp4', '.mov', '.heic', '.gif', '.webp', '.bmp', '.tiff', '.tif']:
                        candidate_name = f"{base}{ext}"
                        if candidate_name in available_media_files:
                            media_filename = candidate_name
                            heuristic_code = "extension_guess_from_supplemental"
                            logger.debug(f"Extension guessed: {{'media_filename': {media_filename!r}}}")
                            break
            
            # Verify that the media file actually exists in our collected files
            logger.debug(f"Validating: {{'media_filename': {media_filename!r}, 'in_set': {media_filename in available_media_files}}}")
            if media_filename not in available_media_files:
                # Media file doesn't exist - this sidecar is orphaned
                unmatched_sidecars.append(json_path)
                logger.warning(
                    f"Sidecar unmatched (media file not found): {{'filename': {json_path.name!r}, 'expected_media': {media_filename!r}, 'available_files': {sorted(list(available_media_files))[:10]}}}"
                )
                continue
            
            key = parent_dir / media_filename
            json_sidecars[key] = json_path
            
            # Track statistics and log
            # Consider it a heuristic if either:
            # 1. A heuristic pattern was used (truncation, plain .json, etc.)
            # 2. Duplicate numbered suffix was used (even with happy path pattern)
            if heuristic_code or has_duplicate_suffix:
                heuristic_matches += 1
                # Build heuristic description
                heuristic_desc = heuristic_code if heuristic_code else "happy_path"
                if has_duplicate_suffix:
                    heuristic_desc = f"{heuristic_desc}+duplicate_numbered_suffix"
                logger.warning(
                    f"Sidecar matched via heuristic: {{'filename': {json_path.name!r}, 'heuristic': {heuristic_desc!r}, 'media_file': {media_filename!r}}}"
                )
            else:
                happy_path_matches += 1
                logger.debug(
                    f"Sidecar matched (happy path): {{'filename': {json_path.name!r}, 'media_file': {media_filename!r}}}"
                )
        else:
            # Could not match this sidecar
            unmatched_sidecars.append(json_path)
            logger.warning(
                f"Sidecar unmatched: {{'filename': {json_path.name!r}}}"
            )
    
    logger.info(
        f"Sidecar matching complete: {{'total': {len(json_sidecars)}, 'happy_path': {happy_path_matches}, 'heuristic': {heuristic_matches}, 'unmatched': {len(unmatched_sidecars)}}}"
    )
    
    # STEP 3: Yield FileInfo objects for all media files
    logger.info("Creating FileInfo objects for media files...")
    files_discovered = 0
    files_with_sidecars = 0
    progress_interval = 1000  # Log every 1000 files
    
    # Time-based progress logging
    discovery_start_time = time.time()
    last_progress_time = discovery_start_time
    time_progress_interval = 2.0  # Log every 2 seconds
    
    for file_path in media_files:
        
        # Get file size
        try:
            file_size = file_path.stat().st_size
        except OSError as e:
            logger.warning(f"Failed to get file size: {{'path': {str(file_path)!r}, 'error': {str(e)!r}}}")
            continue
        
        # Calculate relative path
        # CRITICAL: Use scan_root, not target_media_path, to exclude "Takeout/Google Photos" prefix
        # This makes paths portable (e.g., "Photos from 2023/IMG_1234.jpg" instead of "Takeout/Google Photos/Photos from 2023/IMG_1234.jpg")
        try:
            relative_path = file_path.relative_to(scan_root)
        except ValueError:
            logger.warning(f"File not relative to scan root: {{'path': {str(file_path)!r}}}")
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
                f"Discovery progress: {{'files_found': {files_discovered}, 'with_sidecars': {files_with_sidecars}, 'elapsed_seconds': {elapsed:.1f}, 'files_per_sec': {rate:.0f}}}"
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
        logger.warning(f"No media files discovered: {{'path': {str(target_media_path)!r}}}")
    else:
        total_discovery_time = time.time() - discovery_start_time
        logger.info(
            f"File discovery complete: {{'files_discovered': {files_discovered}, 'with_sidecars': {files_with_sidecars}, 'duration_seconds': {total_discovery_time:.1f}}}"
        )
