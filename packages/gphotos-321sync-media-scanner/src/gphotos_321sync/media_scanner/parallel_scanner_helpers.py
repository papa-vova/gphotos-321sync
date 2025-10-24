"""Helper functions for parallel scanner - content-based matching and orphan reporting."""

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Optional

from .discovery import FileInfo

logger = logging.getLogger(__name__)


def match_orphaned_sidecars(
    target_media_path: Path,
    paired_sidecars: set[Path],
    all_sidecars: set[Path],
    all_media_files: list[FileInfo]
) -> int:
    """Match orphaned sidecars using content-based matching.
    
    Phase 3: For sidecars that couldn't be paired via filename patterns,
    read the JSON 'title' field and match based on content similarity.
    
    IMPORTANT: This function modifies the FileInfo objects in-place by updating
    their json_sidecar_path attribute. It does NOT create new FileInfo objects
    to avoid duplicate processing.
    
    Args:
        target_media_path: Root scan directory
        paired_sidecars: Set of sidecars already paired
        all_sidecars: Set of all discovered sidecars
        all_media_files: List of all discovered media files (modified in-place)
        
    Returns:
        Number of additional pairs found
    """
    orphaned_sidecars = all_sidecars - paired_sidecars
    
    if not orphaned_sidecars:
        return 0
    
    logger.info(f"Phase 3: Content-based matching for {len(orphaned_sidecars)} orphaned sidecars...")
    
    # Build media index by directory for efficient lookup
    media_by_dir = defaultdict(list)
    for file_info in all_media_files:
        media_by_dir[file_info.file_path.parent].append(file_info)
    
    # System files that are not media sidecars
    system_files = {
        'print-subscriptions.json',
        'shared_album_comments.json',
        'user-generated-memory-titles.json'
    }
    
    content_based_matches = 0
    
    for sidecar_path in orphaned_sidecars:
        # Skip system files
        if sidecar_path.name in system_files:
            continue
        
        try:
            with open(sidecar_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            title = data.get('title', '')
            if not title:
                continue
            
            # Find best matching media file in same directory
            parent_dir = sidecar_path.parent
            candidates = media_by_dir.get(parent_dir, [])
            
            if not candidates:
                continue
            
            best_match = None
            best_score = 0.0
            
            title_base = Path(title).stem
            
            for file_info in candidates:
                # Skip if already has a sidecar
                if file_info.json_sidecar_path is not None:
                    continue
                
                media_base = file_info.file_path.stem
                
                # Calculate longest common prefix
                common_len = 0
                for c1, c2 in zip(title_base, media_base):
                    if c1 == c2:
                        common_len += 1
                    else:
                        break
                
                # Similarity score: use minimum length to be more lenient with truncation
                # This handles cases where one filename is truncated version of the other
                min_len = min(len(title_base), len(media_base))
                score = common_len / min_len if min_len > 0 else 0.0
                
                # Require minimum common prefix length to avoid false positives
                if score >= 0.8 and common_len >= 20:  # 80% similarity + min 20 chars
                    if score > best_score:
                        best_score = score
                        best_match = file_info
            
            if best_match:
                # Handle sidecar precedence: ALWAYS prefer filename-based matches
                if best_match.json_sidecar_path is None:
                    # No existing sidecar - attach this one
                    best_match.json_sidecar_path = sidecar_path
                    content_based_matches += 1
                    
                    logger.debug(
                        f"Content-based match: {sidecar_path.name} -> {best_match.file_path.name} "
                        f"(similarity: {best_score:.1%})"
                    )
                else:
                    # File already has a sidecar from filename-based matching
                    # ALWAYS keep the filename-based match as it's more reliable and likely
                    # has richer metadata (geodata, views, people tags, etc.)
                    # Log as WARNING so user can investigate potential data loss
                    logger.warning(
                        f"Multiple sidecars found for same file - keeping filename-based match: "
                        f"{{'media_file': {best_match.file_path.name!r}, "
                        f"'keeping': {best_match.json_sidecar_path.name!r}, "
                        f"'ignoring': {sidecar_path.name!r}}}"
                    )
        
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON: {sidecar_path.name}")
        except Exception as e:
            logger.debug(f"Content-based matching error for {sidecar_path.name}: {e}")
    
    if content_based_matches > 0:
        logger.info(f"Content-based matching complete: {content_based_matches} additional pairs found")
    else:
        logger.info("Content-based matching complete: no additional pairs found")
    
    return content_based_matches


def report_unmatched_files(
    scan_root: Path,
    all_sidecars: set[Path],
    paired_sidecars: set[Path],
    all_media_files: list[FileInfo]
) -> None:
    """Report all unmatched files at end of scan.
    
    Phase 4: Comprehensive reporting of orphaned sidecars and media without sidecars.
    
    Args:
        scan_root: Root scan directory
        all_sidecars: Set of all discovered sidecars
        paired_sidecars: Set of sidecars that were paired
        all_media_files: List of all discovered media files
    """
    orphaned_sidecars = all_sidecars - paired_sidecars
    
    # Categorize orphaned sidecars
    system_files = []
    media_sidecars_orphaned = []
    
    system_file_names = {
        'print-subscriptions.json',
        'shared_album_comments.json',
        'user-generated-memory-titles.json'
    }
    
    for sidecar_path in orphaned_sidecars:
        if sidecar_path.name in system_file_names:
            system_files.append(sidecar_path)
        else:
            media_sidecars_orphaned.append(sidecar_path)
    
    # Count media files without sidecars
    media_without_sidecars = sum(1 for f in all_media_files if f.json_sidecar_path is None)
    
    # Determine scan_root for relative paths
    google_photos_path = scan_root / "Takeout" / "Google Photos"
    path_root = google_photos_path if google_photos_path.exists() else scan_root
    
    # Log structured summary
    if media_sidecars_orphaned or system_files or media_without_sidecars > 0:
        # Log orphaned media sidecars with structured data
        if media_sidecars_orphaned:
            sample_files = []
            for sidecar in sorted(media_sidecars_orphaned)[:10]:
                try:
                    rel_path = str(sidecar.relative_to(path_root))
                    sample_files.append(rel_path)
                except ValueError:
                    sample_files.append(sidecar.name)
            
            logger.warning(
                "Orphaned media sidecars detected",
                extra={
                    "count": len(media_sidecars_orphaned),
                    "sample_files": sample_files,
                    "total_samples": min(10, len(media_sidecars_orphaned)),
                    "possible_causes": [
                        "Media file deleted from Google Photos",
                        "Filename mismatch due to path truncation",
                        "Google Takeout export inconsistency"
                    ]
                }
            )
        
        # Log system files with structured data
        if system_files:
            logger.info(
                "System JSON files found (not media sidecars)",
                extra={
                    "count": len(system_files),
                    "files": [sf.name for sf in sorted(system_files)]
                }
            )
        
        # Log media without sidecars with structured data
        if media_without_sidecars > 0:
            logger.info(
                "Media files without sidecars",
                extra={
                    "count": media_without_sidecars,
                    "normal_reasons": [
                        "Files uploaded before Google Photos added metadata export",
                        "Files imported from other sources",
                        "Files with corrupted or missing metadata"
                    ]
                }
            )
    else:
        logger.info("All files successfully matched - no orphans detected")
