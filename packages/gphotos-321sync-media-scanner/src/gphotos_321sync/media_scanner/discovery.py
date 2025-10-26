"""File discovery for Google Takeout exports.

Discovers all media files and pairs them with JSON sidecars.
Handles Google Takeout directory structure and various edge cases.
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional, List, Dict

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
class ParsedSidecar:
    """Parsed sidecar filename components."""
    filename: str           # "IMG_1234" (without extension)
    extension: str          # "jpg" or "jp" (may be truncated)
    numeric_suffix: str    # "(1)" or "" (may be anywhere)
    full_sidecar_path: Path
    photo_taken_time: Optional[datetime] = None  # from JSON content


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


def discover_files(target_media_path: Path) -> DiscoveryResult:
    """Discover all media files and return structured results.
    
    This is the main public API for file discovery. It scans the directory tree,
    pairs media files with their JSON sidecars, and returns comprehensive statistics.
    
    Args:
        target_media_path: Target media directory to scan (ABSOLUTE path)
        
    Returns:
        DiscoveryResult with files list, sidecar counts, and tracking sets
    """
    files = list(_discover_files_generator(target_media_path))
    
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
        json_sidecar_count=len(all_sidecars),  # Total JSON sidecars found
        paired_sidecars=paired_sidecars,
        all_sidecars=all_sidecars
    )


def _collect_files(scan_root: Path) -> tuple[list[Path], list[Path], dict[Path, set[str]]]:
    """Collect all files in the directory tree.
    
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
    sidecar_index: Dict[str, List[ParsedSidecar]]
) -> FileInfo:
    """Create FileInfo object for a media file.
    
    Args:
        file_path: Path to the media file
        scan_root: Root directory for relative path calculation
        sidecar_index: Dictionary mapping "filename.extension" to list of ParsedSidecar objects
        
    Returns:
        FileInfo object for the media file
    """
    # Calculate relative path from scan_root
    relative_path = file_path.relative_to(scan_root)
    
    # Calculate album folder path (parent of the file)
    album_folder_path = relative_path.parent
    
    # Get file size
    file_size = file_path.stat().st_size
    
    # Find JSON sidecar using new parsing logic
    json_sidecar_path = _match_media_to_sidecar(file_path, sidecar_index)
    
    return FileInfo(
        file_path=file_path,
        relative_path=relative_path,
        album_folder_path=album_folder_path,
        json_sidecar_path=json_sidecar_path,
        file_size=file_size
    )




def _parse_sidecar_filename(sidecar_path: Path) -> ParsedSidecar:
    """Parse sidecar filename into components.
    
    Args:
        sidecar_path: Path to the sidecar file
        
    Returns:
        ParsedSidecar with filename, extension, numeric_suffix components
    """
    # Known media extensions; prefixes count as truncated matches
    KNOWN_EXTS = [
        'jpg','jpeg','jpe','png','gif','webp','heic','heif','bmp','tif','tiff','svg',
        'webm','mp4','mov','avi','m4v','3gp','jfif','dng','cr2','cr3','arw','nef','raf','orf'
    ]
    
    def is_ext_or_prefix(tok: str) -> bool:
        t = tok.lower()
        if not t:
            return False
        return any(e.startswith(t) for e in KNOWN_EXTS)
    
    base = sidecar_path.name
    
    # Require/play nice with trailing .json
    JSON_RE = re.compile(r'\.json\s*$', re.I)
    PAREN_NUM_RE = re.compile(r'\((\d+)\)\s*$')
    
    if not JSON_RE.search(base):
        core = base
        paren_num = ""
    else:
        tmp = JSON_RE.sub('', base)          # remove .json
        m = PAREN_NUM_RE.search(tmp)         # extract "(n)" just before .json
        if m:
            paren_num = f"({m.group(1)})"
            tmp = PAREN_NUM_RE.sub('', tmp)
        else:
            paren_num = ""
        core = tmp
    
    # Strip supplemental tail if present (between extension and .json)
    SUPP_TAIL_RE = re.compile(r'''
        \.
        (?:s|supp(?:lemen(?:t(?:al)?)?)?)    # s / supp / supplemen / supplement / supplemental
        (?:-(?:meta(?:data)?)?)?             # -meta / -metadata (optional)
        -?                                   # optional lone '-'
        \s*$                                 # to end
    ''', re.I | re.X)
    
    core = SUPP_TAIL_RE.sub('', core)
    
    # If no dot at all → no extension; filename is the whole core
    if '.' not in core:
        filename = core if core else ""
        return ParsedSidecar(
            filename=filename,
            extension="",
            numeric_suffix=paren_num,
            full_sidecar_path=sidecar_path
        )
    
    # Split on dots to detect extension cluster from the RIGHT
    tokens = core.split('.')
    # find rightmost token that is an extension or its prefix
    last_ext_idx = -1
    for i, tok in enumerate(tokens):
        if is_ext_or_prefix(tok):
            last_ext_idx = i  # keep updating; end with rightmost
    if last_ext_idx == -1:
        # No extension found: filename is whole core (dots allowed)
        return ParsedSidecar(
            filename=core if core else "",
            extension="",
            numeric_suffix=paren_num,
            full_sidecar_path=sidecar_path
        )
    
    # Walk left to include combined extensions (e.g., svg.png, jpg.webp)
    start_ext_idx = last_ext_idx
    while start_ext_idx - 1 >= 0 and is_ext_or_prefix(tokens[start_ext_idx - 1]):
        start_ext_idx -= 1
    
    # Filename is everything BEFORE the extension cluster (allowing dots in filename)
    filename = ".".join(tokens[:start_ext_idx]) if start_ext_idx > 0 else ""
    filename = filename if filename else ""
    
    # Full extension is the cluster itself
    full_ext_tokens = tokens[start_ext_idx:last_ext_idx + 1]
    full_ext = ".".join(full_ext_tokens) if full_ext_tokens else ""
    
    return ParsedSidecar(
        filename=filename,
        extension=full_ext,
        numeric_suffix=paren_num,
        full_sidecar_path=sidecar_path
    )


def _build_sidecar_index(sidecar_filenames: List[str]) -> Dict[str, List[ParsedSidecar]]:
    """Build index: "album_path/filename.extension" -> List[ParsedSidecar].
    
    Args:
        sidecar_filenames: List of sidecar filenames to parse
        
    Returns:
        Dictionary mapping "album_path/filename.extension" to list of ParsedSidecar objects
    """
    logger.info("Starting sidecar index build")
    
    index: Dict[str, List[ParsedSidecar]] = {}
    
    for sidecar_filename in sidecar_filenames:
        sidecar_path = Path(sidecar_filename)
        parsed = _parse_sidecar_filename(sidecar_path)
        
        # Create key: "album_path/filename.extension"
        # Use relative path from scan_root to avoid absolute path issues
        album_path = sidecar_path.parent.name  # Just the album folder name
        key = f"{album_path}/{parsed.filename}.{parsed.extension}" if parsed.extension else f"{album_path}/{parsed.filename}"
        
        if key not in index:
            index[key] = []
        index[key].append(parsed)
    
    logger.info(f"Finished sidecar index build: {len(index)} unique keys")
    return index


def _match_media_to_sidecar(media_file: Path, sidecar_index: Dict[str, List[ParsedSidecar]]) -> Optional[Path]:
    """Find matching sidecar for media file within one album.
    
    Implements comprehensive matching algorithm with numeric suffix handling.
    
    Args:
        media_file: Path to the media file
        sidecar_index: Dictionary mapping "album_path/filename.extension" to list of ParsedSidecar objects
        
    Returns:
        Path to matching sidecar if found, None otherwise
    """
    logger.debug(f"Starting sidecar discovery for media file: {media_file.name}")
    
    # Extract media filename + extension
    media_stem = media_file.stem
    media_suffix = media_file.suffix.lower()
    
    # Create lookup key: "album_path/filename.extension"
    album_path = media_file.parent.name  # Just the album folder name
    key = f"{album_path}/{media_stem}{media_suffix}"
    
    # Case 1: Exactly one filename + extension match
    if key in sidecar_index and len(sidecar_index[key]) == 1:
        candidate = sidecar_index[key][0]
        
        # Case 1.1: No numeric suffix → success
        if not candidate.numeric_suffix:
            logger.debug(f"Match found (exact): {media_file.name} -> {candidate.full_sidecar_path.name}")
            return candidate.full_sidecar_path
        
        # Case 1.2: Has numeric suffix → check numeric suffix
        if _check_numeric_suffix_match(media_stem, candidate.numeric_suffix):
            logger.debug(f"Match found (numeric suffix): {media_file.name} -> {candidate.full_sidecar_path.name}")
            return candidate.full_sidecar_path
        else:
            logger.info(f"No match: numeric suffix mismatch for {media_file.name}")
            return None
    
    # Case 2: Multiple filename + extension matches
    elif key in sidecar_index and len(sidecar_index[key]) > 1:
        candidates = sidecar_index[key]
        
        # Check if there's ONLY ONE sidecar without numeric suffix
        no_suffix_candidates = [c for c in candidates if not c.numeric_suffix]
        
        if len(no_suffix_candidates) == 1:
            logger.debug(f"Match found (single no-suffix): {media_file.name} -> {no_suffix_candidates[0].full_sidecar_path.name}")
            return no_suffix_candidates[0].full_sidecar_path
        else:
            # Multiple sidecars, no clear winner
            sidecar_names = [c.full_sidecar_path.name for c in candidates]
            logger.error(f"Multiple sidecars for media file: {media_file.name} -> {sidecar_names}")
            return None
    
    # Case 3: No filename + extension match → try alternative patterns
    else:
        return _try_alternative_matching(media_file, sidecar_index)


def _check_numeric_suffix_match(media_stem: str, numeric_suffix: str) -> bool:
    """Check if numeric suffix matches in media filename.
    
    Args:
        media_stem: Media filename without extension
        numeric_suffix: Numeric suffix from sidecar (e.g., "(2)")
        
    Returns:
        True if numeric suffix is found in media filename
    """
    if not numeric_suffix:
        return True
    
    # Extract the number from the suffix (e.g., "(2)" -> "2")
    import re
    match = re.match(r'\((\d+)\)', numeric_suffix)
    if not match:
        return False
    
    number = match.group(1)
    
    # Check two mutually exclusive cases:
    # 1. At the very end: "(n)$"
    # 2. Somewhere within: "(n)\."
    pattern_end = f"\\({number}\\)$"
    pattern_middle = f"\\({number}\\)\\."
    
    return bool(re.search(pattern_end, media_stem) or re.search(pattern_middle, media_stem))


def _try_alternative_matching(media_file: Path, sidecar_index: Dict[str, List[ParsedSidecar]]) -> Optional[Path]:
    """Try alternative matching patterns for unmatched media files.
    
    Args:
        media_file: Path to the media file
        sidecar_index: Dictionary mapping "album_path/filename.extension" to list of ParsedSidecar objects
        
    Returns:
        Path to matching sidecar if found, None otherwise
    """
    media_stem = media_file.stem
    media_suffix = media_file.suffix.lower()
    album_path = media_file.parent.name
    
    # Case 3.1: Check for "-edited" suffix
    media_stem_lower = media_stem.lower()
    edited_patterns = [
        "-edited", "-bearbeitet", "-modifié", "-redigert", "-bewerkt"  # Base patterns in lowercase
    ]
    
    for pattern in edited_patterns:
        if media_stem_lower.endswith(pattern):
            # Find the actual pattern in the original case
            actual_pattern = media_stem[-len(pattern):]
            edited_stem = media_stem[:-len(pattern)]
            
            # Check if there's a numeric suffix after the edited pattern
            # e.g., "photo-edited(2)" -> "photo(2)"
            numeric_suffix_match = _find_numeric_suffix_in_media(edited_stem)
            if numeric_suffix_match:
                # Remove the numeric suffix from edited_stem to get base name
                base_stem = edited_stem.replace(numeric_suffix_match, "")
                if base_stem:  # Make sure we don't end up with empty string
                    key = f"{album_path}/{base_stem}{media_suffix}"
                    if key in sidecar_index:
                        # Found match with edited pattern - apply same logic as Case 1/2
                        return _handle_found_candidates(media_file, sidecar_index[key])
            else:
                # No numeric suffix, just strip the edited pattern
                if edited_stem:  # Make sure we don't end up with empty string
                    key = f"{album_path}/{edited_stem}{media_suffix}"
                    if key in sidecar_index:
                        # Found match with edited pattern - apply same logic as Case 1/2
                        return _handle_found_candidates(media_file, sidecar_index[key])
    
    # Case 3.2: Check for numeric suffix in media filename
    numeric_match = _find_numeric_suffix_in_media(media_stem)
    if numeric_match:
        # Try to find sidecar with matching numeric suffix
        for key, candidates in sidecar_index.items():
            if key.startswith(f"{album_path}/"):
                for candidate in candidates:
                    if candidate.numeric_suffix == numeric_match:
                        logger.debug(f"Match found (numeric suffix match): {media_file.name} -> {candidate.full_sidecar_path.name}")
                        return candidate.full_sidecar_path
    
    # Case 3.3: No match found
    logger.info(f"No match found for media file: {media_file.name}")
    return None


def _find_numeric_suffix_in_media(media_stem: str) -> Optional[str]:
    """Find numeric suffix in media filename.
    
    Args:
        media_stem: Media filename without extension
        
    Returns:
        Numeric suffix if found (e.g., "(2)"), None otherwise
    """
    import re
    
    # Look for numeric suffix pattern "(n)" anywhere in the filename
    match = re.search(r'\(\d+\)', media_stem)
    if match:
        return match.group(0)
    
    return None


def _handle_found_candidates(media_file: Path, candidates: List[ParsedSidecar]) -> Optional[Path]:
    """Handle found candidates using same logic as Cases 1 and 2.
    
    Args:
        media_file: Path to the media file
        candidates: List of ParsedSidecar candidates
        
    Returns:
        Path to matching sidecar if found, None otherwise
    """
    if len(candidates) == 1:
        candidate = candidates[0]
        
        # Case 1.1: No numeric suffix → success
        if not candidate.numeric_suffix:
            logger.debug(f"Match found (alternative, exact): {media_file.name} -> {candidate.full_sidecar_path.name}")
            return candidate.full_sidecar_path
        
        # Case 1.2: Has numeric suffix → check numeric suffix
        if _check_numeric_suffix_match(media_file.stem, candidate.numeric_suffix):
            logger.debug(f"Match found (alternative, numeric suffix): {media_file.name} -> {candidate.full_sidecar_path.name}")
            return candidate.full_sidecar_path
        else:
            logger.info(f"No match: numeric suffix mismatch for {media_file.name}")
            return None
    
    elif len(candidates) > 1:
        # Case 2: Multiple candidates
        no_suffix_candidates = [c for c in candidates if not c.numeric_suffix]
        
        if len(no_suffix_candidates) == 1:
            logger.debug(f"Match found (alternative, single no-suffix): {media_file.name} -> {no_suffix_candidates[0].full_sidecar_path.name}")
            return no_suffix_candidates[0].full_sidecar_path
        else:
            # Multiple sidecars, no clear winner
            sidecar_names = [c.full_sidecar_path.name for c in candidates]
            logger.error(f"Multiple sidecars for media file: {media_file.name} -> {sidecar_names}")
            return None
    
    return None






def _discover_files_generator(
    target_media_path: Path
) -> Iterator[FileInfo]:
    """Internal generator for file discovery.
    
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
    media_files, json_files, all_files = _collect_files(scan_root)
    
    # Build sidecar index for efficient matching
    sidecar_filenames = [str(json_path) for json_path in json_files]
    sidecar_index = _build_sidecar_index(sidecar_filenames)
    
    # Process each media file and yield FileInfo objects
    files_discovered = 0
    files_with_sidecars = 0
    discovery_start_time = time.time()
    last_progress_time = discovery_start_time
    progress_interval = 1000  # Log progress every 1000 files
    time_progress_interval = 30.0  # Log progress every 30 seconds
    
    for file_path in media_files:
        # Create FileInfo object for this media file
        file_info = _create_file_info(file_path, scan_root, sidecar_index)
        
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
