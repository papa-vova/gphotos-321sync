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
class BatchMatchingResult:
    """Result of batch matching operation with phase-by-phase tracking."""
    matches: Dict[Path, Optional[Path]]  # media_file -> sidecar_path
    matched_phase1: set[Path]  # Media files matched in Phase 1
    matched_phase2: set[Path]  # Media files matched in Phase 2
    matched_phase3: set[Path]  # Media files matched in Phase 3
    unmatched_media: set[Path]  # Media files that couldn't be matched
    unmatched_sidecars: set[Path]  # Sidecars that couldn't be matched


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
    """Result of file discovery operation with comprehensive tracking.
    
    Attributes:
        files: List of discovered media files
        json_sidecar_count: Number of unique JSON sidecar files found
        paired_sidecars: Set of sidecar paths that were successfully paired
        all_sidecars: Set of all discovered sidecar paths (for orphan detection)
        
        # Phase-by-phase matching results
        matched_phase1: Set of media files matched in Phase 1 (happy path)
        matched_phase2: Set of media files matched in Phase 2 (numbered files)
        matched_phase3: Set of media files matched in Phase 3 (edited files)
        unmatched_media: Set of media files that couldn't be matched
        unmatched_sidecars: Set of sidecars that couldn't be matched
        
        # File type discovery
        discovered_media: Set of all discovered media files
        discovered_sidecars: Set of all discovered sidecar files
        discovered_metadata: Set of all discovered metadata files
        discovered_other: Set of all other discovered files
    """
    files: List[FileInfo]
    json_sidecar_count: int
    paired_sidecars: set[Path]
    all_sidecars: set[Path]

    # Phase-by-phase matching results
    matched_phase1: set[Path]  # Happy path matches (exact filename, no numeric suffix)
    matched_phase2: set[Path] # Numbered files matches (extract numeric suffix)
    matched_phase3: set[Path] # Edited files matches (strip "-edited")
    unmatched_media: set[Path]
    unmatched_sidecars: set[Path]
    
    # File type discovery
    discovered_media: set[Path]
    discovered_sidecars: set[Path]
    discovered_metadata: set[Path]
    discovered_other: set[Path]


def discover_files(target_media_path: Path) -> DiscoveryResult:
    """Discover all media files and return structured results.
    
    This is the main public API for file discovery. It scans the directory tree,
    pairs media files with their JSON sidecars, and returns comprehensive statistics.
    
    Args:
        target_media_path: Target media directory to scan (ABSOLUTE path)
        
    Returns:
        DiscoveryResult with files list, sidecar counts, and tracking sets
    """
    # Discover all files by type for comprehensive tracking
    google_photos_path = target_media_path / "Takeout" / "Google Photos"
    scan_root = google_photos_path if google_photos_path.exists() else target_media_path
    
    discovered_media = set()
    discovered_sidecars = set()
    discovered_metadata = set()
    discovered_other = set()
    
    # Step 1: Identify files outside album directories (top-level files)
    for file_path in scan_root.rglob("*"):
        if file_path.is_file() and file_path.parent == scan_root:
            # Files at the top level of Google Photos directory
            discovered_other.add(file_path)
    
    # Step 2: Process all files as potential media/sidecars/metadata
    for file_path in scan_root.rglob("*"):
        if file_path.is_file():
            if file_path.suffix.lower() == '.json':
                if file_path.name == "metadata.json":
                    discovered_metadata.add(file_path)
                else:
                    discovered_sidecars.add(file_path)
            elif should_scan_file(file_path):
                discovered_media.add(file_path)
            else:
                discovered_other.add(file_path)
    
    # Step 3: Remove any intersections (files that were already categorized as "other")
    discovered_media -= discovered_other
    discovered_sidecars -= discovered_other
    discovered_metadata -= discovered_other
    
    # Process files and collect phase-by-phase results
    files = []
    paired_sidecars = set()
    matched_phase1 = set()
    matched_phase2 = set()
    matched_phase3 = set()
    unmatched_media = set()
    unmatched_sidecars = set()
    
    # Group media files by album for batch processing
    media_by_album = {}
    for media_file in discovered_media:
        album_path = media_file.parent
        if album_path not in media_by_album:
            media_by_album[album_path] = []
        media_by_album[album_path].append(media_file)
    
    # Process each album with batch matching
    for album_path, album_media_files in media_by_album.items():
        # Build sidecar index for this album
        album_sidecar_index = {}
        for sidecar_path in discovered_sidecars:
            if sidecar_path.parent == album_path:
                parsed = _parse_sidecar_filename(sidecar_path)
                key = f"{parsed.filename}.{parsed.extension}"
                if key not in album_sidecar_index:
                    album_sidecar_index[key] = []
                album_sidecar_index[key].append(parsed)
        
        # Process album with batch algorithm
        batch_result = _match_media_to_sidecar_batch(album_media_files, album_sidecar_index)
        
        # Collect phase-by-phase results
        matched_phase1.update(batch_result.matched_phase1)
        matched_phase2.update(batch_result.matched_phase2)
        matched_phase3.update(batch_result.matched_phase3)
        unmatched_media.update(batch_result.unmatched_media)
        unmatched_sidecars.update(batch_result.unmatched_sidecars)
        
        # Create FileInfo objects from batch results
        for media_file, sidecar_path in batch_result.matches.items():
            file_info = _create_file_info_from_batch_result(media_file, scan_root, sidecar_path)
            files.append(file_info)
            if sidecar_path:
                paired_sidecars.add(sidecar_path)
        
        # CRITICAL FIX: Also create FileInfo objects for unmatched media files
        # These need to be processed even without sidecars for metadata extraction
        for unmatched_media_file in batch_result.unmatched_media:
            file_info = _create_file_info_from_batch_result(unmatched_media_file, scan_root, None)
            files.append(file_info)
    
    return DiscoveryResult(
        files=files,
        json_sidecar_count=len(discovered_sidecars),  # Total JSON sidecars found
        paired_sidecars=paired_sidecars,
        all_sidecars=discovered_sidecars,
        
        # Phase-by-phase matching results
        matched_phase1=matched_phase1,
        matched_phase2=matched_phase2,
        matched_phase3=matched_phase3,
        unmatched_media=unmatched_media,
        unmatched_sidecars=unmatched_sidecars,
        
        # File type discovery
        discovered_media=discovered_media,
        discovered_sidecars=discovered_sidecars,
        discovered_metadata=discovered_metadata,
        discovered_other=discovered_other
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
    
    # Step 1: Identify top-level files (these are not media/sidecars)
    top_level_files = set()
    for file_path in scan_root.rglob("*"):
        if file_path.is_file() and file_path.parent == scan_root:
            top_level_files.add(file_path)
    
    # Step 2: Process all files as potential media/sidecars
    for file_path in scan_root.rglob("*"):
        if file_path.is_dir():
            continue
        
        # Skip top-level files (already identified as "other")
        if file_path in top_level_files:
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


def _create_file_info_from_batch_result(media_file: Path, scan_root: Path, sidecar_path: Optional[Path]) -> FileInfo:
    """Create FileInfo object from batch matching result.
    
    Args:
        media_file: Path to the media file
        scan_root: Root directory for relative path calculation
        sidecar_path: Path to matching sidecar (or None if no match)
        
    Returns:
        FileInfo object
    """
    # Calculate relative paths
    try:
        relative_path = media_file.relative_to(scan_root)
    except ValueError:
        # If media_file is not under scan_root, use the filename
        relative_path = Path(media_file.name)
    
    # Calculate album folder path (parent of relative_path)
    album_folder_path = relative_path.parent if relative_path.parent != Path('.') else Path('.')
    
    # Get file size
    try:
        file_size = media_file.stat().st_size
    except OSError:
        file_size = 0
    
    return FileInfo(
        file_path=media_file,
        relative_path=relative_path,
        album_folder_path=album_folder_path,
        json_sidecar_path=sidecar_path,
        file_size=file_size
    )


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
    """Find matching sidecar for media file using phased algorithm.
    
    Implements systematic matching with exclusion of matched pairs:
    1. Happy path: exact filename match (no numeric suffix)
    2. Numbered files: match with numeric suffix
    3. Edited files: strip "-edited" and match
    
    Args:
        media_file: Path to the media file
        sidecar_index: Dictionary mapping "album_path/filename.extension" to list of ParsedSidecar objects
        
    Returns:
        Path to matching sidecar if found, None otherwise
    """
    logger.debug(f"Starting sidecar discovery for media file: {media_file.name}")
    
    # Extract media filename components
    media_stem = media_file.stem
    media_suffix = media_file.suffix.lower()
    album_path = media_file.parent.name
    
    # Phase 1: Happy path - exact filename match (no numeric suffix)
    match = _try_happy_path_match(media_stem, media_suffix, album_path, sidecar_index)
    if match:
        logger.debug(f"Match found (happy path): {media_file.name} -> {match.name}")
        return match
    
    # Phase 2: Numbered files - extract numeric suffix and match
    match = _try_numbered_files_match(media_stem, media_suffix, album_path, sidecar_index)
    if match:
        logger.debug(f"Match found (numbered): {media_file.name} -> {match.name}")
        return match
    
    # Phase 3: Edited files - strip "-edited" and match
    match = _try_edited_files_match(media_stem, media_suffix, album_path, sidecar_index)
    if match:
        logger.debug(f"Match found (edited): {media_file.name} -> {match.name}")
        return match
    
    # Phase 4: No match found
    logger.info(f"No match found for media file: {media_file.name}")
    return None


def _match_media_to_sidecar_batch(media_files: List[Path], sidecar_index: Dict[str, List[ParsedSidecar]]) -> BatchMatchingResult:
    """Match all media files to sidecars using phased algorithm with exclusion.
    
    Implements the systematic matching algorithm:
    1. Happy path: exact filename match (no numeric suffix)
    2. Numbered files: match with numeric suffix  
    3. Edited files: strip "-edited" and match
    
    Args:
        media_files: List of media file paths in the album
        sidecar_index: Dictionary mapping "filename.extension" to list of ParsedSidecar objects
        
    Returns:
        BatchMatchingResult with matches and phase-by-phase tracking
    """
    matches = {}
    remaining_media = media_files.copy()
    remaining_sidecars = set()
    
    # Build set of all available sidecars
    for sidecar_list in sidecar_index.values():
        for sidecar in sidecar_list:
            remaining_sidecars.add(sidecar.full_sidecar_path)
    
    logger.info(f"Starting batch matching for {len(media_files)} media files in album")
    
    # Phase 1: Happy path - exact filename match (no numeric suffix)
    logger.debug("Phase 1: Happy path matching")
    phase1_matches = []
    for media_file in remaining_media:
        match = _try_happy_path_match_batch(media_file, sidecar_index, remaining_sidecars)
        if match:
            matches[media_file] = match
            phase1_matches.append(media_file)
            remaining_sidecars.discard(match)
            # DEBUG: Log successful match
            logger.debug(f"Phase 1 match: {media_file} -> {match}")
    
    # Remove matched media files
    for media_file in phase1_matches:
        remaining_media.remove(media_file)
    
    logger.debug(f"Phase 1 complete: {len(phase1_matches)} matches")
    
    # Phase 2: Numbered files - extract numeric suffix and match
    logger.debug("Phase 2: Numbered files matching")
    phase2_matches = []
    for media_file in remaining_media:
        match = _try_numbered_files_match_batch(media_file, sidecar_index, remaining_sidecars)
        if match:
            matches[media_file] = match
            phase2_matches.append(media_file)
            remaining_sidecars.discard(match)
            # DEBUG: Log successful match
            logger.debug(f"Phase 2 match: {media_file} -> {match}")
    
    # Remove matched media files
    for media_file in phase2_matches:
        remaining_media.remove(media_file)
    
    logger.debug(f"Phase 2 complete: {len(phase2_matches)} matches")
    
    # Phase 3: Edited files - strip "-edited" and match
    logger.debug("Phase 3: Edited files matching")
    phase3_matches = []
    for media_file in remaining_media:
        match = _try_edited_files_match_batch(media_file, sidecar_index, remaining_sidecars)
        if match:
            matches[media_file] = match
            phase3_matches.append(media_file)
            remaining_sidecars.discard(match)
            # DEBUG: Log successful match
            logger.debug(f"Phase 3 match: {media_file} -> {match}")
    
    # Remove matched media files
    for media_file in phase3_matches:
        remaining_media.remove(media_file)
    
    logger.debug(f"Phase 3 complete: {len(phase3_matches)} matches")
    
    # Phase 4: Log unmatched files with paths
    logger.info(f"Phase 4: {len(remaining_media)} unmatched media files, {len(remaining_sidecars)} unmatched sidecars")
    
    # INFO: Log unmatched media files with paths
    for unmatched_media in remaining_media:
        logger.info(f"Unmatched media: {unmatched_media}")
    
    # INFO: Log unmatched sidecars with paths
    for unmatched_sidecar in remaining_sidecars:
        logger.info(f"Unmatched sidecar: {unmatched_sidecar}")
    
    return BatchMatchingResult(
        matches=matches,
        matched_phase1=set(phase1_matches),
        matched_phase2=set(phase2_matches),
        matched_phase3=set(phase3_matches),
        unmatched_media=set(remaining_media),
        unmatched_sidecars=remaining_sidecars
    )


def _try_happy_path_match_batch(media_file: Path, sidecar_index: Dict[str, List[ParsedSidecar]], remaining_sidecars: set) -> Optional[Path]:
    """Phase 1 batch helper: Happy path matching with exclusion."""
    media_stem = media_file.stem
    media_suffix = media_file.suffix.lower()
    album_path = media_file.parent.name
    
    key = f"{media_stem}{media_suffix}"
    
    if key not in sidecar_index:
        return None
    
    # Look for sidecars with empty numeric suffix that are still available
    no_suffix_candidates = [c for c in sidecar_index[key] 
                           if not c.numeric_suffix and c.full_sidecar_path in remaining_sidecars]
    
    if len(no_suffix_candidates) == 1:
        return no_suffix_candidates[0].full_sidecar_path
    elif len(no_suffix_candidates) > 1:
        logger.error(f"Multiple sidecars without numeric suffix for {media_stem}{media_suffix}: {[c.full_sidecar_path.name for c in no_suffix_candidates]}")
        return None
    
    return None


def _try_numbered_files_match_batch(media_file: Path, sidecar_index: Dict[str, List[ParsedSidecar]], remaining_sidecars: set) -> Optional[Path]:
    """Phase 2 batch helper: Numbered files matching with exclusion."""
    media_stem = media_file.stem
    media_suffix = media_file.suffix.lower()
    album_path = media_file.parent.name
    
    # Extract numeric suffix from media filename
    media_numeric_suffix = _extract_numeric_suffix_from_media(media_stem)
    
    if not media_numeric_suffix:
        return None
    
    # Remove numeric suffix from media stem to get base filename
    base_stem = _remove_numeric_suffix_from_media(media_stem)
    
    # Look for sidecars with base filename and matching numeric suffix that are still available
    key = f"{base_stem}{media_suffix}"
    
    if key not in sidecar_index:
        return None
    
    # Look for sidecars with matching numeric suffix that are still available
    matching_candidates = [c for c in sidecar_index[key] 
                          if c.numeric_suffix == media_numeric_suffix and c.full_sidecar_path in remaining_sidecars]
    
    if len(matching_candidates) == 1:
        return matching_candidates[0].full_sidecar_path
    elif len(matching_candidates) > 1:
        logger.error(f"Multiple sidecars with numeric suffix {media_numeric_suffix} for {media_stem}{media_suffix}: {[c.full_sidecar_path.name for c in matching_candidates]}")
        return None
    
    return None


def _try_edited_files_match_batch(media_file: Path, sidecar_index: Dict[str, List[ParsedSidecar]], remaining_sidecars: set) -> Optional[Path]:
    """Phase 3 batch helper: Edited files matching with exclusion."""
    media_stem = media_file.stem
    media_suffix = media_file.suffix.lower()
    album_path = media_file.parent.name
    
    # Check if filename contains "-edited" (case insensitive)
    if "-edited" not in media_stem.lower():
        return None
    
    # Strip "-edited" from filename (case insensitive)
    base_stem = _strip_edited_from_filename(media_stem)
    
    if not base_stem:
        logger.debug(f"Phase 3: Could not strip '-edited' from {media_stem}")
        return None
    
    # Extract numeric suffix from the base filename
    base_numeric_suffix = _extract_numeric_suffix_from_media(base_stem)
    
    # Remove numeric suffix from base stem to get the actual base filename
    actual_base_stem = _remove_numeric_suffix_from_media(base_stem)
    
    key = f"{actual_base_stem}{media_suffix}"
    
    logger.debug(f"Phase 3: {media_stem} -> base_stem: {base_stem}, actual_base_stem: {actual_base_stem}, key: {key}")
    
    if key not in sidecar_index:
        logger.debug(f"Phase 3: No sidecars found for key {key}")
        return None
    
    # Look for sidecars with matching numeric suffix (or no suffix if base has no suffix) that are still available
    if base_numeric_suffix:
        matching_candidates = [c for c in sidecar_index[key] 
                             if c.numeric_suffix == base_numeric_suffix and c.full_sidecar_path in remaining_sidecars]
    else:
        matching_candidates = [c for c in sidecar_index[key] 
                              if not c.numeric_suffix and c.full_sidecar_path in remaining_sidecars]
    
    logger.debug(f"Phase 3: Found {len(matching_candidates)} candidates for {media_stem}")
    
    if len(matching_candidates) == 1:
        return matching_candidates[0].full_sidecar_path
    elif len(matching_candidates) > 1:
        logger.error(f"Multiple sidecars for edited file {media_stem}{media_suffix} -> {actual_base_stem}{media_suffix}: {[c.full_sidecar_path.name for c in matching_candidates]}")
        return None
    
    return None


def _try_happy_path_match(media_stem: str, media_suffix: str, album_path: str, sidecar_index: Dict[str, List[ParsedSidecar]]) -> Optional[Path]:
    """Phase 1: Happy path - exact filename match (no numeric suffix).
    
    Args:
        media_stem: Media filename without extension
        media_suffix: Media file extension
        album_path: Album folder name
        sidecar_index: Sidecar index
        
    Returns:
        Path to matching sidecar if found, None otherwise
    """
    key = f"{media_stem}{media_suffix}"
    
    if key not in sidecar_index:
        return None
    
    # Look for sidecars with empty numeric suffix
    no_suffix_candidates = [c for c in sidecar_index[key] if not c.numeric_suffix]
    
    if len(no_suffix_candidates) == 1:
        return no_suffix_candidates[0].full_sidecar_path
    elif len(no_suffix_candidates) > 1:
        logger.error(f"Multiple sidecars without numeric suffix for {media_stem}{media_suffix}: {[c.full_sidecar_path.name for c in no_suffix_candidates]}")
        return None
    
    return None


def _try_numbered_files_match(media_stem: str, media_suffix: str, album_path: str, sidecar_index: Dict[str, List[ParsedSidecar]]) -> Optional[Path]:
    """Phase 2: Numbered files - extract numeric suffix and match.
    
    Args:
        media_stem: Media filename without extension
        media_suffix: Media file extension
        album_path: Album folder name
        sidecar_index: Sidecar index
        
    Returns:
        Path to matching sidecar if found, None otherwise
    """
    # Extract numeric suffix from media filename
    media_numeric_suffix = _extract_numeric_suffix_from_media(media_stem)
    
    if not media_numeric_suffix:
        return None
    
    # Remove numeric suffix from media stem to get base filename
    base_stem = _remove_numeric_suffix_from_media(media_stem)
    
    # Look for sidecars with base filename and matching numeric suffix
    key = f"{base_stem}{media_suffix}"
    
    if key not in sidecar_index:
        return None
    
    # Look for sidecars with matching numeric suffix
    matching_candidates = [c for c in sidecar_index[key] if c.numeric_suffix == media_numeric_suffix]
    
    if len(matching_candidates) == 1:
        return matching_candidates[0].full_sidecar_path
    elif len(matching_candidates) > 1:
        logger.error(f"Multiple sidecars with numeric suffix {media_numeric_suffix} for {media_stem}{media_suffix}: {[c.full_sidecar_path.name for c in matching_candidates]}")
        return None
    
    return None


def _try_edited_files_match(media_stem: str, media_suffix: str, album_path: str, sidecar_index: Dict[str, List[ParsedSidecar]]) -> Optional[Path]:
    """Phase 3: Edited files - strip "-edited" and match.
    
    Args:
        media_stem: Media filename without extension
        media_suffix: Media file extension
        album_path: Album folder name
        sidecar_index: Sidecar index
        
    Returns:
        Path to matching sidecar if found, None otherwise
    """
    # Check if filename contains "-edited" (case insensitive)
    if "-edited" not in media_stem.lower():
        return None
    
    # Strip "-edited" from filename (case insensitive)
    base_stem = _strip_edited_from_filename(media_stem)
    
    if not base_stem:
        return None
    
    # Extract numeric suffix from the base filename
    base_numeric_suffix = _extract_numeric_suffix_from_media(base_stem)
    
    # Remove numeric suffix from base stem to get the actual base filename
    actual_base_stem = _remove_numeric_suffix_from_media(base_stem)
    
    key = f"{actual_base_stem}{media_suffix}"
    
    if key not in sidecar_index:
        return None
    
    # Look for sidecars with matching numeric suffix (or no suffix if base has no suffix)
    if base_numeric_suffix:
        matching_candidates = [c for c in sidecar_index[key] if c.numeric_suffix == base_numeric_suffix]
    else:
        matching_candidates = [c for c in sidecar_index[key] if not c.numeric_suffix]
    
    if len(matching_candidates) == 1:
        return matching_candidates[0].full_sidecar_path
    elif len(matching_candidates) > 1:
        logger.error(f"Multiple sidecars for edited file {media_stem}{media_suffix} -> {base_stem}{media_suffix}: {[c.full_sidecar_path.name for c in matching_candidates]}")
        return None
    
    return None


def _extract_numeric_suffix_from_media(media_stem: str) -> Optional[str]:
    """Extract numeric suffix from media filename.
    
    Three mutually exclusive cases:
    1. No suffix
    2. At the very end: "(n)$"
    3. Somewhere within: "(n)\\."
    
    Args:
        media_stem: Media filename without extension
        
    Returns:
        Numeric suffix string (e.g., "(2)") or None if no suffix found
    """
    import re
    
    # Pattern for numeric suffix: "(n)" where n is digits
    pattern = r'\((\d+)\)'
    matches = list(re.finditer(pattern, media_stem))
    
    if not matches:
        return None
    
    # Find the rightmost match (last occurrence)
    last_match = matches[-1]
    suffix_start = last_match.start()
    suffix_end = last_match.end()
    
    # Check if it's at the very end
    if suffix_end == len(media_stem):
        return last_match.group(0)  # Return "(n)"
    
    # Check if it's followed by a dot (somewhere within)
    if suffix_end < len(media_stem) and media_stem[suffix_end] == '.':
        return last_match.group(0)  # Return "(n)"
    
    return None


def _remove_numeric_suffix_from_media(media_stem: str) -> str:
    """Remove numeric suffix from media filename.
    
    Args:
        media_stem: Media filename without extension
        
    Returns:
        Media filename with numeric suffix removed
    """
    import re
    
    # Pattern for numeric suffix: "(n)" where n is digits
    pattern = r'\((\d+)\)'
    
    # Remove the last occurrence of numeric suffix
    return re.sub(pattern, '', media_stem, count=1)


def _strip_edited_from_filename(filename: str) -> Optional[str]:
    """Strip "-edited" from filename (case insensitive).
    
    Args:
        filename: Filename to process
        
    Returns:
        Filename with "-edited" stripped, or None if not found
    """
    import re
    
    # Case insensitive pattern for "-edited"
    pattern = r'-edited'
    
    # Find all occurrences
    matches = list(re.finditer(pattern, filename, re.IGNORECASE))
    
    if not matches:
        return None
    
    # Remove the last occurrence of "-edited"
    last_match = matches[-1]
    stripped = filename[:last_match.start()] + filename[last_match.end():]
    
    return stripped if stripped else None


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
    
    # Group media files by album for batch processing
    albums = {}
    for file_path in media_files:
        album_path = file_path.parent
        if album_path not in albums:
            albums[album_path] = []
        albums[album_path].append(file_path)
    
    # Process each album as a batch using the new algorithm
    files_discovered = 0
    files_with_sidecars = 0
    discovery_start_time = time.time()
    last_progress_time = discovery_start_time
    progress_interval = 1000  # Log progress every 1000 files
    time_progress_interval = 30.0  # Log progress every 30 seconds
    
    for album_path, album_media_files in albums.items():
        logger.info(f"Processing album: {album_path.name}")
        
        # Build album-specific sidecar index
        album_sidecar_index = {}
        for key, sidecar_list in sidecar_index.items():
            # Filter sidecars that belong to this album
            album_sidecars = []
            for sidecar in sidecar_list:
                # Compare the parent directory name of the sidecar with the album path name
                if sidecar.full_sidecar_path.parent.name == album_path.name:
                    album_sidecars.append(sidecar)
            if album_sidecars:
                # Use simple key format for album-specific index
                simple_key = key.split('/')[-1] if '/' in key else key
                album_sidecar_index[simple_key] = album_sidecars
        
        # Process album with batch algorithm
        batch_results = _match_media_to_sidecar_batch(album_media_files, album_sidecar_index)
        
        # Create FileInfo objects from batch results
        for media_file, sidecar_path in batch_results.items():
            file_info = _create_file_info_from_batch_result(media_file, scan_root, sidecar_path)
            
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
