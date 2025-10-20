"""File processor for CPU-bound work.

This module handles CPU-intensive operations that will run in a process pool:
- EXIF extraction
- Resolution extraction
- Video metadata extraction
- CRC32 calculation
- MIME type detection
- Content fingerprint calculation
"""

import logging
from pathlib import Path
from typing import Optional
import zlib

from .metadata.exif_extractor import extract_exif_smart, extract_resolution
from .metadata.video_extractor import extract_video_metadata, is_video_file
from .mime_detector import detect_mime_type
from .fingerprint import compute_content_fingerprint
from .errors import classify_error

logger = logging.getLogger(__name__)


def process_file_cpu_work(
    file_path: Path,
    file_size: int,
    use_exiftool: bool = False,
    use_ffprobe: bool = True
) -> dict:
    """Process a file with CPU-bound operations.
    
    This function is designed to run in a separate process in the parallel
    architecture. It performs all CPU-intensive operations on a single file.
    
    Args:
        file_path: Absolute path to the file
        file_size: Size of the file in bytes
        use_exiftool: Whether to use exiftool for EXIF extraction
        use_ffprobe: Whether to use ffprobe for video metadata
        
    Returns:
        Dictionary with processing results:
        {
            'success': bool,
            'mime_type': str,
            'crc32': str (8 hex chars),
            'content_fingerprint': str (64 hex chars),
            'width': int or None,
            'height': int or None,
            'exif_data': dict,
            'video_data': dict or None,
            'error': str or None,
            'error_category': str or None
        }
        
    Note:
        - All exceptions are caught and returned in the result dict
        - This allows the parallel scanner to continue on errors
        - Errors are logged and recorded in processing_errors table
    """
    result = {
        'success': False,
        'mime_type': None,
        'crc32': None,
        'content_fingerprint': None,
        'width': None,
        'height': None,
        'exif_data': {},
        'video_data': None,
        'error': None,
        'error_category': None
    }
    
    try:
        # Check if file exists first
        if not file_path.exists():
            error_msg = f"File does not exist: {file_path}"
            logger.error(f"File does not exist: {{'path': {str(file_path)!r}}}")
            result['error'] = error_msg
            result['error_category'] = 'io'
            result['success'] = False
            return result
        
        # 1. Detect MIME type (reads magic bytes from file header)
        try:
            mime_type = detect_mime_type(file_path)
            result['mime_type'] = mime_type
        except Exception as e:
            logger.debug(f"MIME type detection failed: {{'path': {str(file_path)!r}, 'error': {str(e)!r}}}")
            # Use a fallback - continue processing
            mime_type = 'application/octet-stream'
            result['mime_type'] = mime_type
        
        # 2. Calculate CRC32 (full file stream)
        try:
            crc32_value = calculate_crc32(file_path)
            result['crc32'] = crc32_value
        except Exception as e:
            logger.debug(f"CRC32 calculation failed: {{'path': {str(file_path)!r}, 'error': {str(e)!r}}}")
            # Not a critical error - continue processing
        
        # 3. Calculate content fingerprint (first 64KB + last 64KB)
        try:
            fingerprint = compute_content_fingerprint(file_path, file_size)
            result['content_fingerprint'] = fingerprint
        except Exception as e:
            logger.debug(f"Content fingerprint calculation failed: {{'path': {str(file_path)!r}, 'error': {str(e)!r}}}")
            # Not a critical error - continue processing
        
        # 4. Extract EXIF metadata (if applicable)
        try:
            exif_data = extract_exif_smart(file_path, use_exiftool)
            result['exif_data'] = exif_data
        except Exception as e:
            logger.debug(f"EXIF extraction failed: {{'path': {str(file_path)!r}, 'error': {str(e)!r}}}")
            # Not a critical error - continue processing
        
        # 5. Extract resolution (width x height)
        # Only try to extract resolution for images, not videos
        if not is_video_file(mime_type):
            try:
                resolution = extract_resolution(file_path, use_exiftool)
                if resolution:
                    result['width'], result['height'] = resolution
            except Exception as e:
                logger.debug(f"Resolution extraction failed: {{'path': {str(file_path)!r}, 'error': {str(e)!r}}}")
                # Not a critical error - continue processing
        
        # 6. Extract video metadata (if video and ffprobe available)
        if is_video_file(mime_type) and use_ffprobe:
            try:
                video_data = extract_video_metadata(file_path)
                result['video_data'] = video_data
                # Extract resolution from video metadata
                if video_data and 'width' in video_data and 'height' in video_data:
                    result['width'] = video_data['width']
                    result['height'] = video_data['height']
            except Exception as e:
                logger.debug(f"Video metadata extraction failed: {{'path': {str(file_path)!r}, 'error': {str(e)!r}}}")
                # Not a critical error - continue processing
        
        result['success'] = True
        
    except Exception as e:
        # Catch all errors and return them in result
        error_msg = str(e)
        error_category = classify_error(e)
        
        logger.error(f"Failed to process file: {{'path': {str(file_path)!r}, 'error': {error_msg!r}}}", exc_info=True)
        
        result['error'] = error_msg
        result['error_category'] = error_category
        result['success'] = False
    
    return result


def calculate_crc32(file_path: Path) -> str:
    """Calculate CRC32 checksum of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        CRC32 checksum as 8-character hex string (e.g., "a1b2c3d4")
        
    Note:
        - Reads file in chunks to handle large files efficiently
        - CRC32 is fast (~1-2 GB/s) for duplicate detection
    """
    crc = 0
    chunk_size = 64 * 1024  # 64KB chunks
    
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            crc = zlib.crc32(chunk, crc)
    
    # Convert to unsigned 32-bit integer and format as 8 hex chars
    crc = crc & 0xFFFFFFFF
    return f"{crc:08x}"
