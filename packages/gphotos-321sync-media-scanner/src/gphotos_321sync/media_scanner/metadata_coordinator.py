"""Metadata coordinator for I/O-bound work.

This module handles I/O-intensive operations that run in worker threads:
- JSON sidecar parsing
- Metadata aggregation (combining CPU results with JSON data)
- Creating database records
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
import uuid

from gphotos_321sync.common import normalize_path
from .discovery import FileInfo
from .metadata.json_parser import parse_json_sidecar
from .metadata.aggregator import aggregate_metadata
from .errors import ParseError

logger = logging.getLogger(__name__)

# UUID5 namespace for media items (deterministic ID generation)
# This ensures the same media item always gets the same UUID across re-imports
# Using RFC 4122 DNS namespace constant - the specific namespace doesn't matter,
# just needs to be consistent across all UUID5 generations in this project
MEDIA_ITEM_NAMESPACE = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')


@dataclass
class MediaItemRecord:
    """Complete media item record ready for database insertion.
    
    This combines all metadata from various sources into a single record.
    """
    media_item_id: str
    relative_path: str
    album_id: str
    title: Optional[str]
    mime_type: Optional[str]
    file_size: int
    crc32: Optional[str]
    content_fingerprint: Optional[str]
    
    # Dimensions
    width: Optional[int]
    height: Optional[int]
    
    # Video-specific
    duration_seconds: Optional[float]
    frame_rate: Optional[float]
    
    # Timestamps
    capture_timestamp: Optional[datetime]
    
    # EXIF metadata
    exif_datetime_original: Optional[datetime]
    exif_datetime_digitized: Optional[datetime]
    exif_gps_latitude: Optional[float]
    exif_gps_longitude: Optional[float]
    exif_gps_altitude: Optional[float]
    exif_camera_make: Optional[str]
    exif_camera_model: Optional[str]
    exif_lens_make: Optional[str]
    exif_lens_model: Optional[str]
    exif_focal_length: Optional[float]
    exif_f_number: Optional[float]
    exif_iso: Optional[int]
    exif_exposure_time: Optional[str]
    exif_orientation: Optional[int]
    
    # Google Photos metadata
    google_description: Optional[str]
    google_geo_latitude: Optional[float]
    google_geo_longitude: Optional[float]
    google_geo_altitude: Optional[float]
    
    # Status
    status: str = 'present'
    scan_run_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            'media_item_id': self.media_item_id,
            'relative_path': self.relative_path,
            'album_id': self.album_id,
            'title': self.title,
            'mime_type': self.mime_type,
            'file_size': self.file_size,
            'crc32': self.crc32,
            'content_fingerprint': self.content_fingerprint,
            'width': self.width,
            'height': self.height,
            'duration_seconds': self.duration_seconds,
            'frame_rate': self.frame_rate,
            'capture_timestamp': self.capture_timestamp,
            'exif_datetime_original': self.exif_datetime_original,
            'exif_datetime_digitized': self.exif_datetime_digitized,
            'exif_gps_latitude': self.exif_gps_latitude,
            'exif_gps_longitude': self.exif_gps_longitude,
            'exif_gps_altitude': self.exif_gps_altitude,
            'exif_camera_make': self.exif_camera_make,
            'exif_camera_model': self.exif_camera_model,
            'exif_lens_make': self.exif_lens_make,
            'exif_lens_model': self.exif_lens_model,
            'exif_focal_length': self.exif_focal_length,
            'exif_f_number': self.exif_f_number,
            'exif_iso': self.exif_iso,
            'exif_exposure_time': self.exif_exposure_time,
            'exif_orientation': self.exif_orientation,
            'google_description': self.google_description,
            'google_geo_latitude': self.google_geo_latitude,
            'google_geo_longitude': self.google_geo_longitude,
            'google_geo_altitude': self.google_geo_altitude,
            'status': self.status,
            'scan_run_id': self.scan_run_id,
        }


def coordinate_metadata(
    file_info: FileInfo,
    metadata_ext: dict,
    album_id: str,
    scan_run_id: str
) -> MediaItemRecord:
    """Coordinate metadata from multiple sources.
    
    This function runs in a worker thread and performs I/O operations:
    - Parses JSON sidecar (if present)
    - Combines CPU results with JSON metadata
    - Applies metadata aggregation (precedence rules)
    - Creates MediaItemRecord for database insertion
    
    Args:
        file_info: File discovery information
        metadata_ext: Metadata extraction results (MIME, CRC32, fingerprint, EXIF, video)
        album_id: Album ID for this file
        scan_run_id: Current scan run ID
        
    Returns:
        MediaItemRecord ready for database insertion
        
    Raises:
        Exception: Any errors during processing (caller should handle)
    """
    try:
        # 1. Parse JSON sidecar if present (I/O operation)
        json_metadata = {}
        if file_info.json_sidecar_path:
            try:
                json_metadata = parse_json_sidecar(file_info.json_sidecar_path)
                logger.debug(f"Parsed JSON sidecar for {file_info.relative_path}")
            except (ParseError, Exception) as e:
                logger.warning(f"Failed to parse JSON sidecar for {file_info.relative_path}: {e}")
                # Continue without JSON metadata
        
        # 2. Extract data from metadata extraction result
        exif_data = metadata_ext.get('exif_data', {})
        video_data = metadata_ext.get('video_data', {})
        
        # 3. Aggregate metadata (apply precedence rules: JSON > EXIF > filename > NULL)
        try:
            aggregated = aggregate_metadata(
                file_path=file_info.file_path,
                json_metadata=json_metadata,
                exif_data=exif_data,
                video_data=video_data
            )
        except Exception as e:
            logger.error(f"Failed to aggregate metadata for {file_info.relative_path}: {e}", exc_info=True)
            # Use empty aggregated metadata as fallback
            aggregated = {}
        
        # 4. Generate media_item_id (UUID5 - deterministic based on canonical tuple)
        # Canonical tuple: (relative_path, photoTakenTime, file_size, creationTime)
        # This ensures the same media item gets the same UUID on re-imports
        try:
            media_item_id = _generate_media_item_id(
                relative_path=file_info.relative_path,
                json_metadata=json_metadata,
                file_size=file_info.file_size
            )
        except Exception as e:
            logger.error(f"Failed to generate media_item_id for {file_info.relative_path}: {e}", exc_info=True)
            # Generate fallback UUID based on file path only
            media_item_id = str(uuid.uuid5(MEDIA_ITEM_NAMESPACE, file_info.relative_path))
        
        # 5. Extract EXIF fields
        exif_datetime_original = exif_data.get('datetime_original')
        exif_datetime_digitized = exif_data.get('datetime_digitized')
        exif_gps = exif_data.get('gps', {})
        exif_camera_make = exif_data.get('camera_make')
        exif_camera_model = exif_data.get('camera_model')
        exif_lens_make = exif_data.get('lens_make')
        exif_lens_model = exif_data.get('lens_model')
        exif_focal_length = exif_data.get('focal_length')
        exif_f_number = exif_data.get('f_number')
        exif_iso = exif_data.get('iso')
        exif_exposure_time = exif_data.get('exposure_time')
        exif_orientation = exif_data.get('orientation')
        
        # 6. Extract Google Photos metadata from JSON
        google_description = json_metadata.get('description')
        google_geo = json_metadata.get('geoData', {})
        
        # 7. Extract video metadata
        duration_seconds = video_data.get('duration') if video_data else None
        frame_rate = video_data.get('frame_rate') if video_data else None
        
        # 8. Create MediaItemRecord
        record = MediaItemRecord(
            media_item_id=media_item_id,
            relative_path=normalize_path(file_info.relative_path),
            album_id=album_id,
            title=aggregated.get('title'),
            mime_type=metadata_ext.get('mime_type'),
            file_size=file_info.file_size,
            crc32=metadata_ext.get('crc32'),
            content_fingerprint=metadata_ext.get('content_fingerprint'),
            width=metadata_ext.get('width'),
            height=metadata_ext.get('height'),
            duration_seconds=duration_seconds,
            frame_rate=frame_rate,
            capture_timestamp=aggregated.get('capture_timestamp'),
            exif_datetime_original=exif_datetime_original,
            exif_datetime_digitized=exif_datetime_digitized,
            exif_gps_latitude=exif_gps.get('latitude'),
            exif_gps_longitude=exif_gps.get('longitude'),
            exif_gps_altitude=exif_gps.get('altitude'),
            exif_camera_make=exif_camera_make,
            exif_camera_model=exif_camera_model,
            exif_lens_make=exif_lens_make,
            exif_lens_model=exif_lens_model,
            exif_focal_length=exif_focal_length,
            exif_f_number=exif_f_number,
            exif_iso=exif_iso,
            exif_exposure_time=exif_exposure_time,
            exif_orientation=exif_orientation,
            google_description=google_description,
            google_geo_latitude=google_geo.get('latitude'),
            google_geo_longitude=google_geo.get('longitude'),
            google_geo_altitude=google_geo.get('altitude'),
            status='present',
            scan_run_id=scan_run_id
        )
        
        return record
        
    except Exception as e:
        logger.error(
            f"Critical error in coordinate_metadata for {file_info.relative_path}: {e}",
            exc_info=True
        )
        # Re-raise to let worker thread handle it
        raise


def _generate_media_item_id(
    relative_path: str,
    json_metadata: dict,
    file_size: int
) -> str:
    """Generate deterministic UUID5 for media item.
    
    Uses canonical tuple: (relative_path, photoTakenTime, file_size, creationTime)
    This ensures the same media item gets the same UUID across re-imports.
    
    Args:
        relative_path: Normalized relative path within Takeout
        json_metadata: Parsed JSON sidecar metadata
        file_size: File size in bytes
        
    Returns:
        UUID5 string
    """
    # Normalize path (forward slashes, strip leading/trailing)
    normalized_path = normalize_path(relative_path)
    
    # Extract timestamps from JSON metadata
    # Handle both dict format (real JSON) and string format (test fixtures)
    photo_taken_time = ''
    if 'photoTakenTime' in json_metadata:
        pt = json_metadata['photoTakenTime']
        if isinstance(pt, dict):
            photo_taken_time = pt.get('timestamp', '')
        else:
            photo_taken_time = str(pt)
    
    creation_time = ''
    if 'creationTime' in json_metadata:
        ct = json_metadata['creationTime']
        if isinstance(ct, dict):
            creation_time = ct.get('timestamp', '')
        else:
            creation_time = str(ct)
    
    # Build canonical string
    # Format: relative_path|photoTakenTime|file_size|creationTime
    components = [
        normalized_path,
        str(photo_taken_time),
        str(file_size),
        str(creation_time)
    ]
    canonical = '|'.join(components)
    
    # Generate UUID5
    return str(uuid.uuid5(MEDIA_ITEM_NAMESPACE, canonical))
