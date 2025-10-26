"""Helper functions for parallel scanner - orphan reporting."""

import logging
from pathlib import Path

from .discovery import FileInfo

logger = logging.getLogger(__name__)


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
    media_without_sidecars = [f for f in all_media_files if f.json_sidecar_path is None]
    
    if orphaned_sidecars:
        logger.info(f"Found {len(orphaned_sidecars)} orphaned sidecars (no matching media file)")
        for sidecar in sorted(orphaned_sidecars):
            logger.info(f"  Orphaned sidecar: {sidecar.relative_to(scan_root)}")
    
    if media_without_sidecars:
        logger.info(f"Found {len(media_without_sidecars)} media files without sidecars")
        for file_info in sorted(media_without_sidecars, key=lambda f: f.relative_path):
            logger.info(f"  Media without sidecar: {file_info.relative_path}")
    
    if not orphaned_sidecars and not media_without_sidecars:
        logger.info("Perfect matching: all media files have sidecars, all sidecars have media files")