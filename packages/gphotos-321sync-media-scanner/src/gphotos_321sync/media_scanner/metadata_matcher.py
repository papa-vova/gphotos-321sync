"""Metadata-based sidecar matching fallback.

This module provides fallback matching logic when filename-based matching fails.
It uses metadata timestamps (photoTakenTime from JSON sidecar vs EXIF from media file)
to match sidecars to media files in the SAME folder.

Use cases:
- Numbered duplicates: Match correct (N) sidecar to (N) media file by timestamp
  Example: "4_13_12 - 1.supplemental-metadata(1).json" → "4_13_12 - 1(1).jpg"
- Files with ambiguous naming patterns where filename matching is insufficient
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from gphotos_321sync.media_scanner.metadata.exif_extractor import extract_exif_smart
from gphotos_321sync.media_scanner.metadata.video_extractor import extract_video_metadata

logger = logging.getLogger(__name__)


def parse_sidecar_timestamp(sidecar_path: Path) -> Optional[datetime]:
    """Extract photoTakenTime timestamp from Google Takeout JSON sidecar.
    
    Args:
        sidecar_path: Path to .supplemental-metadata.json file
        
    Returns:
        Timezone-aware datetime object, or None if parsing fails
    """
    try:
        with open(sidecar_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Google Takeout format: {"photoTakenTime": {"timestamp": "1234567890"}}
        photo_taken = data.get('photoTakenTime', {})
        timestamp_str = photo_taken.get('timestamp')
        
        if not timestamp_str:
            logger.debug(f"No photoTakenTime.timestamp in sidecar: {{'path': {str(sidecar_path)!r}}}")
            return None
        
        # Parse Unix timestamp (seconds since epoch)
        timestamp = int(timestamp_str)
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        
        return dt
        
    except (json.JSONDecodeError, ValueError, OSError) as e:
        logger.warning(f"Failed to parse sidecar timestamp: {{'path': {str(sidecar_path)!r}, 'error': {str(e)!r}}}")
        return None


def parse_media_timestamp(media_path: Path, use_exiftool: bool = False, use_ffprobe: bool = False) -> Optional[datetime]:
    """Extract timestamp from media file EXIF/metadata.
    
    Args:
        media_path: Path to media file (image or video)
        use_exiftool: Whether to use ExifTool for RAW/HEIC formats
        use_ffprobe: Whether to use FFprobe for video metadata
        
    Returns:
        Timezone-aware datetime object, or None if parsing fails
    """
    try:
        # Try EXIF extraction for images
        exif_data = extract_exif_smart(media_path, use_exiftool=use_exiftool)
        
        # Check for DateTimeOriginal (preferred)
        if 'datetime_original' in exif_data:
            timestamp_str = exif_data['datetime_original']
            # Parse ISO format: "2020-01-01T12:00:00+00:00"
            return datetime.fromisoformat(timestamp_str)
        
        # Fallback to DateTimeDigitized
        if 'datetime_digitized' in exif_data:
            timestamp_str = exif_data['datetime_digitized']
            return datetime.fromisoformat(timestamp_str)
        
        # Try video metadata extraction if ffprobe is available
        if use_ffprobe:
            try:
                video_data = extract_video_metadata(media_path)
                if video_data and 'creation_time' in video_data:
                    # Video metadata returns ISO format timestamp
                    return datetime.fromisoformat(video_data['creation_time'])
            except Exception as e:
                logger.debug(f"Video metadata extraction failed: {{'path': {str(media_path)!r}, 'error': {str(e)!r}}}")
        
        logger.debug(f"No timestamp found in media file: {{'path': {str(media_path)!r}}}")
        return None
        
    except Exception as e:
        logger.debug(f"Failed to parse media timestamp: {{'path': {str(media_path)!r}, 'error': {str(e)!r}}}")
        return None


def timestamps_match(ts1: Optional[datetime], ts2: Optional[datetime], tolerance_seconds: int = 1) -> bool:
    """Check if two timestamps match within tolerance.
    
    Args:
        ts1: First timestamp
        ts2: Second timestamp
        tolerance_seconds: Maximum difference in seconds to consider a match
        
    Returns:
        True if timestamps match within tolerance, False otherwise
    """
    if ts1 is None or ts2 is None:
        return False
    
    diff = abs((ts1 - ts2).total_seconds())
    return diff <= tolerance_seconds


def match_sidecar_by_metadata(
    sidecar_path: Path,
    candidate_media_paths: list[Path],
    tolerance_seconds: int = 1,
    use_exiftool: bool = False,
    use_ffprobe: bool = False
) -> Optional[Path]:
    """Match a sidecar to a media file using metadata timestamps.
    
    This is a fallback matching strategy when filename-based matching fails.
    
    Args:
        sidecar_path: Path to unmatched sidecar
        candidate_media_paths: List of potential media files to match against
        tolerance_seconds: Maximum timestamp difference to consider a match
        use_exiftool: Whether to use ExifTool for RAW/HEIC formats
        use_ffprobe: Whether to use FFprobe for video metadata
        
    Returns:
        Path to matched media file, or None if no match found
        
    Example:
        >>> sidecar = Path("Photos from 2012/DSC_3767.JPG.supplemental-metadata.json")
        >>> candidates = [
        ...     Path("Лис/DSC_3767.JPG"),
        ...     Path("Лис/DSC_3768.JPG")
        ... ]
        >>> match = match_sidecar_by_metadata(sidecar, candidates)
        >>> # Returns Path("Лис/DSC_3767.JPG") if timestamps match
    """
    # Parse sidecar timestamp
    sidecar_ts = parse_sidecar_timestamp(sidecar_path)
    if sidecar_ts is None:
        logger.debug(f"Cannot match by metadata - no timestamp in sidecar: {{'path': {str(sidecar_path)!r}}}")
        return None
    
    # Try to match against each candidate
    for media_path in candidate_media_paths:
        media_ts = parse_media_timestamp(media_path, use_exiftool=use_exiftool, use_ffprobe=use_ffprobe)
        
        if timestamps_match(sidecar_ts, media_ts, tolerance_seconds):
            logger.info(
                f"Metadata-based match found: {{'sidecar': {str(sidecar_path)!r}, 'media': {str(media_path)!r}, 'timestamp': {sidecar_ts.isoformat()}}}"
            )
            return media_path
    
    logger.debug(
        f"No metadata match found: {{'sidecar': {str(sidecar_path)!r}, 'candidates': {len(candidate_media_paths)}, 'timestamp': {sidecar_ts.isoformat()}}}"
    )
    return None
