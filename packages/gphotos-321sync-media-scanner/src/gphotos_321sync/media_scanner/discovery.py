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
    
    # Find JSON sidecar using sophisticated matching logic
    json_sidecar_path = _handle_edited_files_and_duplicates(file_path, json_sidecars)
    
    return FileInfo(
        file_path=file_path,
        relative_path=relative_path,
        album_folder_path=album_folder_path,
        json_sidecar_path=json_sidecar_path,
        file_size=file_size
    )


def _match_supplemental_metadata_patterns(
    json_path: Path, 
    available_files: set[str]
) -> tuple[Optional[str], Optional[str]]:
    """Match .supplemental-metadata.json patterns (full and truncated variants).
    
    Args:
        json_path: Path to the JSON sidecar file
        available_files: Set of available media filenames in the same directory
        
    Returns:
        Tuple of (media_filename, heuristic_code) if match found, (None, None) otherwise
    """
    filename = json_path.name
    
    # Extract duplicate numbered suffix (e.g., "(1)", "(2)") before .json if present
    # Pattern: filename.ext.supplemental-metadata(1).json
    # The media file will be: filename(1).ext
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
    filename_len = len(filename)
    
    # HEURISTIC: Sidecars with duplicate suffix but no extension in base name
    # Pattern: [UNSET].supplemental-metadata(1).json -> [UNSET](1).jpg
    #          [Some Name].supplemental-metadata(2).json -> [Some Name](2).png
    # Google Photos creates these for files without proper metadata
    # MUST come BEFORE happy path because base name has no extension
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
                if candidate_name in available_files:
                    return candidate_name, "no_extension_with_duplicate_suffix"
    
    # HAPPY PATH: Full .supplemental-metadata.json (standard Google Takeout pattern)
    if filename_len > 30 and '.supplemental-metadata' in filename:
        # Full pattern: photo.jpg.supplemental-metadata.json (27 chars + base)
        media_filename = filename.split('.supplemental-metadata')[0]
        logger.debug(f"Happy path matched: {{'filename': {filename!r}, 'media_filename': {media_filename!r}, 'duplicate_suffix': {duplicate_suffix!r}}}")
        # No heuristic code - this is happy path
    # HEURISTIC: Truncated .supplemental-* patterns (filename truncation)
    elif filename_len > 28 and '.supplemental-metadat' in filename:
        media_filename = filename.split('.supplemental-metadat')[0]
        heuristic_code = "truncated_supplemental_metadat"
    elif filename_len > 25 and '.supplemental-metad' in filename:
        media_filename = filename.split('.supplemental-metad')[0]
        heuristic_code = "truncated_supplemental_metad"
    elif filename_len > 24 and '.supplemental-meta' in filename:
        media_filename = filename.split('.supplemental-meta')[0]
        heuristic_code = "truncated_supplemental_meta"
    elif filename_len > 21 and '.supplemental-me' in filename:
        media_filename = filename.split('.supplemental-me')[0]
        heuristic_code = "truncated_supplemental_me"
    elif '.supplemental-' in filename:
        media_filename = filename.split('.supplemental-')[0]
        heuristic_code = "truncated_supplemental_other"
    
    # HEURISTIC: .supplemen* variants (heavily truncated)
    elif filename_len > 18 and '.supplemen' in filename:
        media_filename = filename.split('.supplemen')[0]
        heuristic_code = "truncated_supplemen"
    elif filename_len > 17 and '.suppleme' in filename:
        media_filename = filename.split('.suppleme')[0]
        heuristic_code = "truncated_suppleme"
    elif filename_len > 16 and '.supplem' in filename:
        media_filename = filename.split('.supplem')[0]
        heuristic_code = "truncated_supplem"
    elif filename_len > 15 and '.supple' in filename:
        media_filename = filename.split('.supple')[0]
        heuristic_code = "truncated_supple"
    elif filename_len > 14 and '.suppl' in filename:
        media_filename = filename.split('.suppl')[0]
        heuristic_code = "truncated_suppl"
    elif filename_len > 13 and '.supp' in filename:
        media_filename = filename.split('.supp')[0]
        heuristic_code = "truncated_supp"
    
    # HEURISTIC: Very heavily truncated (rare)
    elif filename_len > 12 and '.sup.' in filename and filename.endswith('.json'):
        media_filename = filename.split('.sup.')[0]
        heuristic_code = "truncated_sup"
    elif filename_len > 11 and '.su.' in filename and filename.endswith('.json'):
        media_filename = filename.split('.su.')[0]
        heuristic_code = "truncated_su"
    elif filename_len > 10 and '.s.' in filename and filename.endswith('.json'):
        media_filename = filename.split('.s.')[0]
        heuristic_code = "truncated_s"
    
    # HEURISTIC: Duplicate sidecars without .supplemental-metadata
    # Pattern: "Screenshot_2022-04-21(1).json" -> "Screenshot_2022-04-21.jpg"
    # This handles duplicate JSON sidecars that don't have the supplemental-metadata pattern
    # MUST come before plain_json_extension fallback
    elif has_duplicate_suffix and '.supplemental' not in filename:
        # Extract base name without (N).json
        base = json_path.stem.rsplit('(', 1)[0]  # Remove (N) suffix
        # Try common extensions
        for ext in ['.jpg', '.jpeg', '.png', '.mp4', '.mov', '.heic', '.gif', '.webp']:
            candidate_name = f"{base}{ext}"
            if candidate_name in available_files:
                return candidate_name, "duplicate_without_supplemental"
    
    # HEURISTIC: Alternative .json pattern (for very long filenames, rare)
    # This is a fallback - should come AFTER all other specific patterns
    elif filename.endswith('.json'):
        # Alternative pattern: photo.json (without .supplemental prefix)
        # Used when media filename is extremely long and gets truncated by Google's export system
        # Do PREFIX matching - find media file that starts with the sidecar base name
        base = filename[:-5]  # Remove .json
        # Find ALL media files that start with this base
        candidates = [f for f in available_files if f.startswith(base) and f != filename]
        # Only match if there's exactly ONE candidate (unambiguous)
        if len(candidates) == 1:
            return candidates[0], "plain_json_extension"
        elif len(candidates) > 1:
            # Ambiguous - multiple files match this prefix
            logger.warning(
                f"Ambiguous prefix match for sidecar: {{'filename': {json_path.name!r}, 'prefix': {base!r}, 'candidates': {candidates}}}"
            )
    
    else:
        return None, None
    
    # Process the matched filename
    if 'media_filename' in locals():
        # STEP 1: Add duplicate suffix FIRST (before extension guessing)
        # If there's a duplicate suffix (e.g., "(1)"), insert it before the extension
        # Example: image.png + (1) -> image(1).png
        if duplicate_suffix:
            logger.debug(f"Adding duplicate suffix: {{'media_filename': {media_filename!r}, 'duplicate_suffix': {duplicate_suffix!r}}}")
            
            # Check if media_filename has a valid extension
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
        
        # STEP 2: Extension guessing (AFTER duplicate suffix is added)
        # Pattern: "04.03.12 - 10(1)" -> "04.03.12 - 10(1).jpg"
        # This handles cases where the sidecar name doesn't include the media extension
        # ONLY apply if the media file doesn't exist as-is
        if media_filename not in available_files:
            # Check if media_filename has a valid media extension
            media_ext = media_filename.split('.')[-1].lower() if '.' in media_filename else ''
            valid_exts = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'heic', 'tiff', 'tif', 
                         'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv', '3gp', 'm4v'}
            
            if media_ext not in valid_exts:
                # Media filename has no valid extension - use prefix matching to find it
                base = media_filename
                # Find ALL media files that start with base + '.' (excluding JSON files)
                candidates = [f for f in available_files if f.startswith(base + '.') and not f.endswith('.json')]
                # Only match if there's exactly ONE candidate (unambiguous)
                if len(candidates) == 1:
                    media_filename = candidates[0]
                    heuristic_code = "extension_guess_from_supplemental"
                    logger.debug(f"Extension guessed via prefix match: {{'media_filename': {media_filename!r}}}")
                elif len(candidates) > 1:
                    # Ambiguous - multiple files match this prefix
                    logger.warning(
                        f"Ambiguous extension match for sidecar: {{'filename': {json_path.name!r}, 'base': {base!r}, 'candidates': {candidates}}}"
                    )
                    # Don't pair - let it fall through to unmatched
                    return None, None
        
        # Only return if we found a valid media file
        if media_filename in available_files:
            return media_filename, heuristic_code if 'heuristic_code' in locals() else None
    
    return None, None


def _handle_edited_files_and_duplicates(
    file_path: Path, 
    json_sidecars: dict[Path, Path]
) -> Optional[Path]:
    """Handle edited files and duplicate patterns for sidecar lookup.
    
    Args:
        file_path: Path to the media file
        json_sidecars: Dictionary mapping media files to their JSON sidecars
        
    Returns:
        Path to JSON sidecar if found, None otherwise
    """
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
    # This handles cases where the sidecar filename itself is truncated by Google's export system
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
    
    return json_sidecar_path


def parse_sidecar_filename(sidecar_path: Path) -> ParsedSidecar:
    """Parse sidecar filename into components using the exact logic from the provided script.
    
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


def build_sidecar_index(sidecar_filenames: List[str]) -> Dict[str, List[ParsedSidecar]]:
    """Build index: "filename.extension" -> List[ParsedSidecar].
    
    Args:
        sidecar_filenames: List of sidecar filenames to parse
        
    Returns:
        Dictionary mapping "filename.extension" to list of ParsedSidecar objects
    """
    logger.info("Starting sidecar index build")
    
    index: Dict[str, List[ParsedSidecar]] = {}
    
    for sidecar_filename in sidecar_filenames:
        sidecar_path = Path(sidecar_filename)
        parsed = parse_sidecar_filename(sidecar_path)
        
        # Create key: "filename.extension"
        key = f"{parsed.filename}.{parsed.extension}" if parsed.extension else parsed.filename
        
        if key not in index:
            index[key] = []
        index[key].append(parsed)
    
    logger.info(f"Finished sidecar index build: {len(index)} unique keys")
    return index


def match_media_to_sidecar(media_file: Path, sidecar_index: Dict[str, List[ParsedSidecar]]) -> Optional[Path]:
    """Find matching sidecar for media file within one album.
    
    Args:
        media_file: Path to the media file
        sidecar_index: Dictionary mapping "filename.extension" to list of ParsedSidecar objects
        
    Returns:
        Path to matching sidecar if found, None otherwise
    """
    logger.debug(f"Starting sidecar discovery for media file: {media_file.name}")
    
    # Extract media filename + extension
    media_stem = media_file.stem
    media_suffix = media_file.suffix.lower()
    
    # Create lookup key
    key = f"{media_stem}{media_suffix}"
    
    # Look up in sidecar_index
    if key not in sidecar_index:
        logger.debug(f"No sidecar candidates found for: {key}")
        return None
    
    candidates = sidecar_index[key]
    
    if len(candidates) == 1:
        candidate = candidates[0]
        logger.debug(f"Single sidecar candidate found: {candidate.full_sidecar_path.name}")
        
        # For single candidate, we still need to check timestamps if available
        # TODO: Implement timestamp comparison
        logger.debug(f"Assigned sidecar to media file: {candidate.full_sidecar_path.name}")
        return candidate.full_sidecar_path
    
    elif len(candidates) > 1:
        logger.warning(f"Multiple sidecar candidates found for: {key}")
        for i, candidate in enumerate(candidates):
            logger.debug(f"Candidate {i+1}: {candidate.full_sidecar_path.name}")
        
        # TODO: Implement timestamp comparison to find best match
        # For now, return the first candidate
        best_candidate = candidates[0]
        logger.debug(f"Assigned sidecar to media file: {best_candidate.full_sidecar_path.name}")
        return best_candidate.full_sidecar_path
    
    return None


def handle_unmatched_files(unmatched_media: List[Path], unmatched_sidecars: List[Path]) -> Dict:
    """Process unmatched files - placeholder for now.
    
    Args:
        unmatched_media: List of unmatched media files
        unmatched_sidecars: List of unmatched sidecar files
        
    Returns:
        Dictionary with processing results
    """
    # TODO: Implement later
    logger.info(f"Processing {len(unmatched_media)} unmatched media files and {len(unmatched_sidecars)} unmatched sidecars")
    return {}


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
        
        # Try supplemental metadata patterns first (most common)
        media_filename, heuristic_code = _match_supplemental_metadata_patterns(json_path, available_media_files)
        
        if media_filename:
            # Only pair if we found a valid media file
            if media_filename in available_media_files:
                key = parent_dir / media_filename
                json_sidecars[key] = json_path
                
                # Track statistics and log
                # Consider it a heuristic if either:
                # 1. A heuristic pattern was used (truncation, plain .json, etc.)
                # 2. Duplicate numbered suffix was used (even with happy path pattern)
                if heuristic_code:
                    heuristic_matches += 1
                    logger.warning(
                        f"Sidecar matched via heuristic: {{'filename': {json_path.name!r}, 'heuristic': {heuristic_code!r}, 'media_file': {media_filename!r}}}"
                    )
                else:
                    happy_path_matches += 1
                    logger.debug(
                        f"Sidecar matched (happy path): {{'filename': {json_path.name!r}, 'media_file': {media_filename!r}}}"
                    )
            else:
                # Could not find matching media file - this sidecar is orphaned
                unmatched_sidecars.append(json_path)
                logger.debug(
                    f"Sidecar unmatched (media file not found): {{'filename': {json_path.name!r}, 'expected_media': {media_filename!r}}}"
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
