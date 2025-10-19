"""Test helper functions for creating test data.

IMPORTANT: Tests use auto_commit=True for convenience.
Production code (writer thread) uses auto_commit=False for batch commits.
"""

from gphotos_321sync.media_scanner.metadata_coordinator import MediaItemRecord


def create_media_item_record(**kwargs) -> MediaItemRecord:
    """
    Create a MediaItemRecord for testing with sensible defaults.
    
    Args:
        **kwargs: Override any MediaItemRecord fields
        
    Returns:
        MediaItemRecord instance
        
    Example:
        record = create_media_item_record(
            media_item_id='test-id',
            relative_path='Photos/test.jpg',
            album_id='album-id',
            file_size=1024,
            scan_run_id='scan-id'
        )
    """
    defaults = {
        'media_item_id': None,
        'relative_path': None,
        'album_id': None,
        'title': None,
        'mime_type': None,
        'file_size': 0,
        'crc32': None,
        'content_fingerprint': None,
        'width': None,
        'height': None,
        'duration_seconds': None,
        'frame_rate': None,
        'capture_timestamp': None,
        'exif_datetime_original': None,
        'exif_datetime_digitized': None,
        'exif_gps_latitude': None,
        'exif_gps_longitude': None,
        'exif_gps_altitude': None,
        'exif_camera_make': None,
        'exif_camera_model': None,
        'exif_lens_make': None,
        'exif_lens_model': None,
        'exif_focal_length': None,
        'exif_f_number': None,
        'exif_iso': None,
        'exif_exposure_time': None,
        'exif_orientation': None,
        'google_description': None,
        'google_geo_latitude': None,
        'google_geo_longitude': None,
        'google_geo_altitude': None,
        'status': 'present',
        'scan_run_id': None,
    }
    
    # Override defaults with provided kwargs
    defaults.update(kwargs)
    
    return MediaItemRecord(**defaults)
