"""Metadata aggregation with precedence rules."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def aggregate_metadata(
    file_path: Path,
    json_metadata: Optional[Dict[str, Any]] = None,
    exif_data: Optional[Dict[str, Any]] = None,
    video_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Aggregate metadata from multiple sources with precedence rules.
    
    Precedence order:
    1. EXIF/IPTC from media file (if reliable)
    2. Google JSON sidecar (fallback when EXIF is unreliable)
    3. Filename parsing
    4. NULL (unknown)
    
    Args:
        file_path: Path to media file
        json_metadata: Metadata from JSON sidecar
        exif_data: EXIF metadata from image
        video_data: Metadata from video file
        
    Returns:
        Dictionary with aggregated metadata ready for database insertion
    """
    result = {}
    
    # Initialize with empty dicts if None
    json_metadata = json_metadata or {}
    exif_data = exif_data or {}
    video_data = video_data or {}
    
    # Title: JSON > filename
    result['title'] = (
        json_metadata.get('title') or
        file_path.stem
    )
    
    # Description: JSON only
    result['description'] = json_metadata.get('description')
    
    # Capture timestamp: EXIF (if reliable) > JSON > filename > NULL
    result['capture_timestamp'] = _aggregate_timestamp(
        json_metadata, exif_data, file_path
    )
    
    # GPS coordinates: JSON > EXIF
    gps_data = _aggregate_gps(json_metadata, exif_data)
    result.update(gps_data)
    
    # Dimensions: video_data > exif_data
    result['width'] = video_data.get('width') or exif_data.get('width')
    result['height'] = video_data.get('height') or exif_data.get('height')
    
    # Video-specific metadata
    result['duration_seconds'] = video_data.get('duration_seconds')
    result['frame_rate'] = video_data.get('frame_rate')
    
    # EXIF metadata (camera, lens, exposure settings)
    result['exif_datetime_original'] = exif_data.get('datetime_original')
    result['exif_datetime_digitized'] = exif_data.get('datetime_digitized')
    result['exif_camera_make'] = exif_data.get('camera_make')
    result['exif_camera_model'] = exif_data.get('camera_model')
    result['exif_lens_make'] = exif_data.get('lens_make')
    result['exif_lens_model'] = exif_data.get('lens_model')
    result['exif_focal_length'] = exif_data.get('focal_length')
    result['exif_f_number'] = exif_data.get('f_number')
    result['exif_exposure_time'] = exif_data.get('exposure_time')
    result['exif_iso'] = exif_data.get('iso')
    result['exif_orientation'] = exif_data.get('orientation')
    result['exif_flash'] = exif_data.get('flash')
    result['exif_white_balance'] = exif_data.get('white_balance')
    
    # EXIF GPS (separate from aggregated GPS for reference)
    result['exif_gps_latitude'] = exif_data.get('gps_latitude')
    result['exif_gps_longitude'] = exif_data.get('gps_longitude')
    result['exif_gps_altitude'] = exif_data.get('gps_altitude')
    
    # Google Photos metadata
    result['google_description'] = json_metadata.get('description')
    
    # People tags (handled separately in database)
    # Not included in result dict - will be processed by scanner
    
    return result


def _aggregate_timestamp(
    json_metadata: Dict[str, Any],
    exif_data: Dict[str, Any],
    file_path: Path
) -> Optional[str]:
    """
    Aggregate timestamp from multiple sources.
    
    Precedence: EXIF (if reliable) > JSON > filename > NULL
    
    Args:
        json_metadata: JSON sidecar metadata
        exif_data: EXIF metadata
        file_path: Path to file
        
    Returns:
        ISO format timestamp string or None
    """
    # 1. EXIF DateTimeOriginal (if reliable)
    if 'datetime_original' in exif_data and _is_reliable_exif_timestamp(exif_data['datetime_original']):
        return exif_data['datetime_original']
    
    # 2. EXIF DateTimeDigitized (if reliable)
    if 'datetime_digitized' in exif_data and _is_reliable_exif_timestamp(exif_data['datetime_digitized']):
        return exif_data['datetime_digitized']
    
    # 3. JSON photoTakenTime (fallback when EXIF is unreliable)
    if 'photoTakenTime' in json_metadata:
        return json_metadata['photoTakenTime']
    
    # 4. JSON creationTime (fallback when EXIF is unreliable)
    if 'creationTime' in json_metadata:
        return json_metadata['creationTime']
    
    # 5. Parse from filename
    filename_timestamp = _parse_timestamp_from_filename(file_path.name)
    if filename_timestamp:
        return filename_timestamp
    
    # 6. NULL (unknown)
    return None


def _aggregate_gps(
    json_metadata: Dict[str, Any],
    exif_data: Dict[str, Any]
) -> Dict[str, Optional[float]]:
    """
    Aggregate GPS coordinates from multiple sources.
    
    Precedence: JSON > EXIF
    
    Args:
        json_metadata: JSON sidecar metadata
        exif_data: EXIF metadata
        
    Returns:
        Dictionary with google_geo_data_* fields
    """
    result = {
        'google_geo_data_latitude': None,
        'google_geo_data_longitude': None,
        'google_geo_data_altitude': None,
        'google_geo_data_latitude_span': None,
        'google_geo_data_longitude_span': None,
    }
    
    # Check JSON geoData
    if 'geoData' in json_metadata:
        geo = json_metadata['geoData']
        result['google_geo_data_latitude'] = geo.get('latitude')
        result['google_geo_data_longitude'] = geo.get('longitude')
        result['google_geo_data_altitude'] = geo.get('altitude')
        result['google_geo_data_latitude_span'] = geo.get('latitudeSpan')
        result['google_geo_data_longitude_span'] = geo.get('longitudeSpan')
        return result
    
    # Fallback to EXIF GPS (stored in separate fields, not google_geo_data_*)
    # EXIF GPS is stored in exif_gps_* fields by the aggregator
    
    return result


def _parse_timestamp_from_filename(filename: str) -> Optional[str]:
    """
    Parse timestamp from filename patterns.
    
    Common patterns:
    - IMG_20130608_143022.jpg -> 2013-06-08 14:30:22
    - VID_20130608_143022.mp4 -> 2013-06-08 14:30:22
    - 20130608_143022.jpg -> 2013-06-08 14:30:22
    - 2013-06-08 14.30.22.jpg -> 2013-06-08 14:30:22
    
    Args:
        filename: Filename to parse
        
    Returns:
        ISO format timestamp string or None
    """
    # Pattern: IMG_YYYYMMDD_HHMMSS or VID_YYYYMMDD_HHMMSS
    pattern1 = r'(?:IMG|VID)_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})'
    match = re.search(pattern1, filename)
    if match:
        year, month, day, hour, minute, second = match.groups()
        try:
            dt = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second), tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            pass
    
    # Pattern: YYYYMMDD_HHMMSS
    pattern2 = r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})'
    match = re.search(pattern2, filename)
    if match:
        year, month, day, hour, minute, second = match.groups()
        try:
            dt = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second), tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            pass
    
    # Pattern: YYYY-MM-DD HH.MM.SS (spaces and dots)
    pattern3 = r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2})\.(\d{2})\.(\d{2})'
    match = re.search(pattern3, filename)
    if match:
        year, month, day, hour, minute, second = match.groups()
        try:
            dt = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second), tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            pass
    
    # Pattern: YYYY-MM-DD (date only)
    pattern4 = r'(\d{4})-(\d{2})-(\d{2})'
    match = re.search(pattern4, filename)
    if match:
        year, month, day = match.groups()
        try:
            dt = datetime(int(year), int(month), int(day), tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            pass
    
    return None


def _is_reliable_exif_timestamp(timestamp) -> bool:
    """
    Check if EXIF timestamp is reliable and not trivial.
    
    EXIF timestamps are considered unreliable if they are:
    - Default camera timestamps (1970-01-01, 1980-01-01, etc.)
    - Future timestamps (more than 1 year from now)
    - Very old timestamps (before 1990, before digital cameras)
    - Invalid or malformed timestamps
    
    Args:
        timestamp: ISO format timestamp string or datetime object
        
    Returns:
        True if timestamp is reliable, False if trivial/unreliable
    """
    if not timestamp:
        return False
    
    try:
        # Handle both datetime objects and strings
        if isinstance(timestamp, datetime):
            dt = timestamp
        else:
            # Parse the timestamp - handle both with and without timezone
            if timestamp.endswith('Z'):
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            elif '+' in timestamp or timestamp.count('-') > 2:  # Has timezone info
                dt = datetime.fromisoformat(timestamp)
            else:
                # No timezone info - assume UTC
                dt = datetime.fromisoformat(timestamp + '+00:00')
        
        # Check for default/trivial timestamps
        trivial_timestamps = [
            datetime(1970, 1, 1, tzinfo=timezone.utc),  # Unix epoch
            datetime(1980, 1, 1, tzinfo=timezone.utc),  # GPS epoch
            datetime(2000, 1, 1, tzinfo=timezone.utc),  # Y2K default
            datetime(2001, 1, 1, tzinfo=timezone.utc),  # Common default
        ]
        
        for trivial in trivial_timestamps:
            if abs((dt - trivial).total_seconds()) < 60:  # Within 1 minute
                return False
        
        # Check for very old timestamps (before digital cameras were common)
        if dt.year < 1990:
            return False
        
        # Check for future timestamps (more than 1 year from now)
        now = datetime.now(timezone.utc)
        if dt > now:
            # Allow up to 1 year in the future (timezone issues, etc.)
            if (dt - now).days > 365:
                return False
        
        # Check for suspiciously recent timestamps (likely default)
        # If timestamp is within 1 minute of a round hour on Jan 1st, it's likely default
        if (dt.month == 1 and dt.day == 1 and 
            dt.minute == 0 and dt.second == 0):
            return False
        
        return True
        
    except (ValueError, TypeError):
        # Invalid timestamp format
        return False
